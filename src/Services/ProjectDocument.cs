using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
namespace SemaphoreTenantConfigurator.Services;

public sealed class WizardChoices
{
    public string ProjectName { get; set; } = "";
    public string TenantSlug { get; set; } = "";
    public string ApplicationId { get; set; } = "";
    public string DatabaseType { get; set; } = "";
    public string DatasetId { get; set; } = "";
    public string TtlMinutes { get; set; } = "15";
    public bool AddTenantGroup { get; set; } = true;
    public bool AddTenantSurvey { get; set; } = true;
    public bool DisableSchedules { get; set; } = true;
    public bool DisableIntegrations { get; set; } = true;
    public string RepositoryUrl { get; set; } = "";
    public string RepositoryBranch { get; set; } = "";
}
public sealed class ResourceChoice
{
    public string Name { get; set; } = "";
    public bool Included { get; set; } = true;
    public string Label => Name;
}
public sealed class ValueRow
{
    public string Key { get; set; } = "";
    public string Value { get; set; } = "";
    public string Type { get; set; } = "Text";
}
public sealed class ProjectDocument
{
    public JsonObject Original { get; }
    public JsonObject Working { get; }
    public string SourceName => Original["meta"]?["name"]?.ToString() ?? "Unbenannt";
    public ProjectDocument(JsonObject backup)
    {
        Original = (JsonObject)backup.DeepClone();
        Working = (JsonObject)backup.DeepClone();
    }
    public static JsonObject ParseBackup(string text)
    {
        var parsed = JsonNode.Parse(text) as JsonObject;
        if (parsed?["meta"] is not JsonObject meta || string.IsNullOrWhiteSpace(meta["name"]?.ToString()))
            throw new InvalidOperationException("Keine Semaphore-Projektbackup-Datei: meta.name fehlt.");
        return parsed;
    }
    public static JsonArray List(JsonObject obj, string section) => obj[section] as JsonArray ?? new JsonArray();
    public static JsonObject? Find(JsonObject obj, string section, string name)
        => List(obj, section).OfType<JsonObject>().FirstOrDefault(e => e["name"]?.ToString() == name);
    public static string GetGroupValues(JsonObject group) => group["json"]?.ToString() ?? "{}";
    public static void SetGroupValues(JsonObject group, JsonObject values) => group["json"] = values.ToJsonString();
    public static JsonObject ParseGroupValues(JsonObject group)
        => JsonNode.Parse(GetGroupValues(group)) as JsonObject ?? throw new InvalidOperationException($"Gruppe '{group["name"]}' enthält kein JSON-Objekt.");
    public static string NextName(JsonObject root, string section, string name)
    {
        var used = List(root, section).OfType<JsonObject>().Select(e => e["name"]?.ToString()).ToHashSet(StringComparer.OrdinalIgnoreCase);
        if (!used.Contains(name)) return name;
        for (var n = 2; ; n++) if (!used.Contains($"{name}-{n}")) return $"{name}-{n}";
    }
    public static IReadOnlyList<string> SurveyOptions(JsonObject root, string surveyKey)
    {
        foreach (var template in List(root, "templates").OfType<JsonObject>())
            foreach (var survey in (template["survey_vars"] as JsonArray ?? new()).OfType<JsonObject>())
                if (survey["name"]?.ToString() == surveyKey)
                    return (survey["values"] as JsonArray ?? new()).OfType<JsonObject>().Select(x => x["value"]?.ToString() ?? "").Where(x => x.Length > 0).Distinct().ToList();
        return Array.Empty<string>();
    }
    public static JsonObject Prepare(JsonObject source, WizardChoices choice, IEnumerable<ResourceChoice> tasks, IEnumerable<ResourceChoice> groups)
    {
        var result = (JsonObject)source.DeepClone();
        if (result["meta"] is not JsonObject meta) throw new InvalidOperationException("meta fehlt.");
        meta["name"] = choice.ProjectName.Trim();
        var selectedTasks = tasks.Where(t => t.Included).Select(t => t.Name).ToHashSet(StringComparer.Ordinal);
        var selectedGroups = groups.Where(g => g.Included).Select(g => g.Name).ToHashSet(StringComparer.Ordinal);
        if (result["templates"] is null) result["templates"] = new JsonArray();
        if (result["environments"] is null) result["environments"] = new JsonArray();
        var allTasks = List(result, "templates");
        for (int i = allTasks.Count - 1; i >= 0; i--)
            if (!selectedTasks.Contains(allTasks[i]?["name"]?.ToString() ?? "")) allTasks.RemoveAt(i);
        var allGroups = List(result, "environments");
        for (int i = allGroups.Count - 1; i >= 0; i--)
            if (!selectedGroups.Contains(allGroups[i]?["name"]?.ToString() ?? "")) allGroups.RemoveAt(i);
        var firstRepo = List(result, "repositories").OfType<JsonObject>().FirstOrDefault();
        if (firstRepo is not null)
        {
            if (!string.IsNullOrWhiteSpace(choice.RepositoryUrl)) firstRepo["git_url"] = choice.RepositoryUrl.Trim();
            if (!string.IsNullOrWhiteSpace(choice.RepositoryBranch)) firstRepo["git_branch"] = choice.RepositoryBranch.Trim();
        }
        string tenantGroupName = "";
        if (choice.AddTenantGroup)
        {
            tenantGroupName = NextName(result, "environments", "Tenant-" + choice.TenantSlug);
            var values = new JsonObject { ["tenant_slug"] = choice.TenantSlug };
            if (!string.IsNullOrWhiteSpace(choice.ApplicationId)) values["application_id"] = choice.ApplicationId;
            if (!string.IsNullOrWhiteSpace(choice.DatabaseType)) values["database_type"] = choice.DatabaseType;
            if (!string.IsNullOrWhiteSpace(choice.DatasetId)) values["dataset_id"] = choice.DatasetId;
            allGroups.Add(new JsonObject { ["name"] = tenantGroupName, ["json"] = values.ToJsonString(), ["env"] = "{}" });
        }
        foreach (var template in allTasks.OfType<JsonObject>())
        {
            var envNames = template["environments"] as JsonArray;
            if (choice.AddTenantGroup)
            {
                envNames ??= new JsonArray();
                if (template["environments"] is null) template["environments"] = envNames;
                envNames.Add(tenantGroupName);
            }
            if (envNames is not null)
                for (int i = envNames.Count - 1; i >= 0; i--)
                    if (envNames[i]?.ToString() != tenantGroupName && !selectedGroups.Contains(envNames[i]?.ToString() ?? "")) envNames.RemoveAt(i);
            var surveys = template["survey_vars"] as JsonArray;
            if (surveys is null) { surveys = new JsonArray(); template["survey_vars"] = surveys; }
            var updates = new Dictionary<string, string> { ["tenant_slug"] = choice.TenantSlug };
            if (!string.IsNullOrWhiteSpace(choice.ApplicationId)) updates["application_id"] = choice.ApplicationId;
            if (!string.IsNullOrWhiteSpace(choice.DatabaseType)) updates["database_type"] = choice.DatabaseType;
            if (!string.IsNullOrWhiteSpace(choice.DatasetId)) updates["dataset_id"] = choice.DatasetId;
            if (!string.IsNullOrWhiteSpace(choice.TtlMinutes)) updates["ttl_minutes"] = choice.TtlMinutes;
            foreach (var survey in surveys.OfType<JsonObject>())
            {
                var key = survey["name"]?.ToString() ?? "";
                if (updates.TryGetValue(key, out var value)) survey["default_value"] = value;
            }
            if (choice.AddTenantSurvey && !surveys.OfType<JsonObject>().Any(s => s["name"]?.ToString() == "tenant_slug"))
                surveys.Add(new JsonObject { ["name"] = "tenant_slug", ["title"] = "Tenant-ID", ["description"] = "Technische Kennung dieses Mandanten", ["type"] = "", ["required"] = true, ["default_value"] = choice.TenantSlug, ["values"] = new JsonArray() });
        }
        // Statt automatisch neue Deployments anzustoßen, Zeitpläne und Webhooks auf Wunsch entfernen.
        if (choice.DisableSchedules) result["schedules"] = new JsonArray();
        if (choice.DisableIntegrations)
        {
            result["integrations"] = new JsonArray();
            result["integration_aliases"] = new JsonArray();
        }
        return result;
    }
    public static (List<string> Errors, List<string> Warnings) Validate(JsonObject root)
    {
        var errors = new List<string>(); var warnings = new List<string>();
        if (string.IsNullOrWhiteSpace(root["meta"]?["name"]?.ToString())) errors.Add("Projektname fehlt.");
        foreach (var section in new[] { "templates", "environments", "inventories", "repositories", "keys" })
        {
            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var item in List(root, section).OfType<JsonObject>())
            {
                var name = item["name"]?.ToString() ?? "";
                if (name.Length == 0) errors.Add($"{section}: Eintrag ohne Namen.");
                else if (!names.Add(name)) errors.Add($"{section}: '{name}' ist doppelt.");
            }
        }
        var groups = List(root, "environments").OfType<JsonObject>().Select(g => g["name"]?.ToString()).ToHashSet();
        var repos = List(root, "repositories").OfType<JsonObject>().Select(g => g["name"]?.ToString()).ToHashSet();
        var invs = List(root, "inventories").OfType<JsonObject>().Select(g => g["name"]?.ToString()).ToHashSet();
        foreach (var group in List(root, "environments").OfType<JsonObject>())
            foreach (var field in new[] { "env", "json" })
                try { if (JsonNode.Parse(group[field]?.ToString() ?? "{}") is not JsonObject) errors.Add($"Gruppe {group["name"]}: {field} ist kein JSON-Objekt."); }
                catch (System.Text.Json.JsonException) { errors.Add($"Gruppe {group["name"]}: {field} enthält ungültiges JSON."); }
        foreach (var task in List(root, "templates").OfType<JsonObject>())
        {
            var name = task["name"]?.ToString();
            if (!repos.Contains(task["repository"]?.ToString())) errors.Add($"Task {name}: Repository fehlt.");
            if (!invs.Contains(task["inventory"]?.ToString())) errors.Add($"Task {name}: Inventory fehlt.");
            foreach (var group in (task["environments"] as JsonArray ?? new()).Select(e => e?.ToString()))
                if (!groups.Contains(group)) errors.Add($"Task {name}: Variablengruppe '{group}' fehlt.");
            foreach (var survey in (task["survey_vars"] as JsonArray ?? new()).OfType<JsonObject>())
            {
                var def = survey["default_value"]?.ToString() ?? "";
                if (survey["type"]?.ToString() == "enum" && def.Length > 0 && !(survey["values"] as JsonArray ?? new()).OfType<JsonObject>().Any(v => v["value"]?.ToString() == def))
                    errors.Add($"Task {name}: Dropdown-Standardwert '{def}' für {survey["name"]} ist keine gültige Option.");
            }
        }
        foreach (var key in List(root, "keys").OfType<JsonObject>()) if (key["type"]?.ToString() != "none") warnings.Add($"Key '{key["name"]}': geheime Inhalte nach Restore prüfen.");
        if (List(root, "schedules").Count > 0) warnings.Add("Aktive Zeitpläne müssen im Zielprojekt überprüft werden.");
        if (List(root, "integrations").Count > 0) warnings.Add("Integrationen/Webhooks nach Restore prüfen.");
        return (errors, warnings);
    }
    public static bool ValidTenantSlug(string slug) => Regex.IsMatch(slug, "^[a-z0-9][a-z0-9-]{1,30}$") && !slug.EndsWith('-');
}
