using System.IO;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
namespace SemaphoreTenantConfigurator.Services;
public sealed record GroupPreset(string Title, string Description, JsonObject Group, bool Custom)
{
    public string Display => (Custom ? "Eigene · " : "Standard · ") + Title;
}
public static class Presets
{
    private static GroupPreset New(string title, string desc, string name, string values) => new(title, desc, new JsonObject { ["name"] = name, ["json"] = values, ["env"] = "{}" }, false);
    public static List<GroupPreset> All()
    {
        var list = new List<GroupPreset>
        {
            New("Leere Gruppe", "Neue Variablengruppe ohne vordefinierte Felder.", "Neue-Variablengruppe", "{}"),
            New("Deployment / Ports", "Ports und Zeitlimits für temporäre Testumgebungen.", "Deployment-Defaults", "{\"host_bind_address\":\"0.0.0.0\",\"host_port_range_start\":18080,\"host_port_range_end\":18179,\"readiness_timeout_seconds\":300,\"compose_operation_timeout_seconds\":600}"),
            New("Container Registry", "Registry-Konfiguration ohne Passwort oder Token.", "Registry", "{\"registry_host\":\"\",\"registry_username\":\"\",\"image_repository\":\"\",\"application_release_id\":\"prod-latest\"}"),
            New("PostgreSQL", "Datenbankkonfiguration; Passwort gehört in Key Store/Vault.", "PostgreSQL", "{\"postgres_image\":\"postgres:17\",\"postgres_user\":\"postgres\",\"postgres_db\":\"app\"}"),
            New("MariaDB", "Datenbankkonfiguration ohne Geheimnisse.", "MariaDB", "{\"mariadb_image\":\"mariadb:11\",\"mariadb_database\":\"app\",\"mariadb_user\":\"app\"}"),
            New("MySQL", "Datenbankkonfiguration ohne Geheimnisse.", "MySQL", "{\"mysql_image\":\"mysql:8.4\",\"mysql_database\":\"app\",\"mysql_user\":\"app\"}"),
            New("Vault", "Vault-URL und Mounts ohne Role ID oder Secret ID.", "Vault-Verbindung", "{\"vault_url\":\"\",\"vault_kv_mount\":\"kv\",\"vault_auth_mount\":\"semaphore-ansible\"}"),
            New("E-Mail", "SMTP-Relay und Absender ohne Zugangsdaten.", "Mail-Konfiguration", "{\"deployment_mail_sender\":\"\",\"mail_host\":\"\",\"mail_port\":25,\"mail_secure\":\"never\"}")
        };
        var folder = Path.Combine(AppSettings.Root, "Presets");
        if (!Directory.Exists(folder)) return list;
        foreach (var file in Directory.EnumerateFiles(folder, "*.json"))
        {
            try
            {
                var item = JsonNode.Parse(File.ReadAllText(file)) as JsonObject;
                if (item?["group"] is JsonObject group && group["name"] is not null)
                    list.Add(new GroupPreset(item["title"]?.ToString() ?? group["name"]!.ToString(), item["description"]?.ToString() ?? "", (JsonObject)group.DeepClone(), true));
            }
            catch (Exception ex) when (ex is System.Text.Json.JsonException or IOException) { }
        }
        return list;
    }
    private static readonly Regex SecretName = new("password|passwd|passwort|token|secret|private.?key|credential|role.?id|api.?key|crypto.?salt|access.?key", RegexOptions.IgnoreCase | RegexOptions.Compiled);
    public static void SaveCustom(JsonObject group, string title, string description)
    {
        if (string.IsNullOrWhiteSpace(title)) throw new InvalidOperationException("Preset-Titel fehlt.");
        var values = ProjectDocument.ParseGroupValues(group);
        if (ContainsSecret(values)) throw new InvalidOperationException("Preset enthält möglicherweise Zugangsdaten. Bitte zunächst Secrets aus der Variablengruppe entfernen.");
        var folder = Path.Combine(AppSettings.Root, "Presets");
        Directory.CreateDirectory(folder);
        var json = new JsonObject { ["schema_version"] = 1, ["title"] = title.Trim(), ["description"] = description.Trim(), ["group"] = group.DeepClone() };
        File.WriteAllText(Path.Combine(folder, Guid.NewGuid().ToString("N") + ".json"), json.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
    }
    private static bool ContainsSecret(JsonNode? node)
    {
        if (node is JsonObject obj) return obj.Any(x => SecretName.IsMatch(x.Key) || ContainsSecret(x.Value));
        if (node is JsonArray a) return a.Any(ContainsSecret);
        return false;
    }
}
