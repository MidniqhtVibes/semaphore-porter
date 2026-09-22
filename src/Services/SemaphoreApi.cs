using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;
namespace SemaphoreTenantConfigurator.Services;

public sealed record ServerProject(int Id, string Name)
{
    public string Display => $"{Name}   ·   #{Id}";
}
public sealed class SemaphoreApi
{
    public string BaseUrl { get; set; } = "";
    public string Token { get; set; } = "";
    public string ProxyMode { get; set; } = "Windows-Anmeldung";
    public string ProxyUrl { get; set; } = "";
    public NetworkCredential? ManualCredential { get; set; }
    public string LastDiagnostic { get; private set; } = "";

    private HttpClient CreateClient()
    {
        var handler = new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false };
        switch (ProxyMode)
        {
            case "Ohne Proxy": handler.UseProxy = false; break;
            case "Manuell":
                if (!Uri.TryCreate(ProxyUrl, UriKind.Absolute, out var proxyUri) || !(proxyUri.Scheme == "http" || proxyUri.Scheme == "https"))
                    throw new InvalidOperationException("Manueller Proxy: vollständige Adresse einschließlich http:// und Port eintragen.");
                handler.UseProxy = true;
                handler.Proxy = new WebProxy(proxyUri) { Credentials = ManualCredential };
                break;
            default:
                handler.UseProxy = true;
                handler.Proxy = WebRequest.GetSystemWebProxy();
                handler.Proxy.Credentials = CredentialCache.DefaultNetworkCredentials;
                break;
        }
        return new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(25) };
    }
    private Uri GetUri(string relative)
    {
        if (!Uri.TryCreate(BaseUrl.Trim(), UriKind.Absolute, out var uri) || (uri.Scheme != "https" && uri.Scheme != "http"))
            throw new InvalidOperationException("Semaphore-Server: vollständige URL mit https:// eingeben.");
        var path = uri.AbsolutePath.TrimEnd('/');
        if (path.EndsWith("/api", StringComparison.OrdinalIgnoreCase)) path = path[..^4];
        return new UriBuilder(uri) { Path = path + "/api/" + relative.TrimStart('/'), Query = "", Fragment = "" }.Uri;
    }
    private static Uri GetSafeRedirect(Uri current, Uri original, Uri target)
    {
        if (!string.Equals(target.Host, original.Host, StringComparison.OrdinalIgnoreCase) || (current.Scheme == "https" && target.Scheme != "https") || target.Port != current.Port)
            throw new InvalidOperationException("API-Weiterleitung auf anderen Host, Port oder unsicheres Protokoll abgelehnt. Endgültige Server-URL eintragen.");
        var root = original.AbsolutePath[..(original.AbsolutePath.IndexOf("/api/", StringComparison.OrdinalIgnoreCase) + 5)];
        if (!target.AbsolutePath.StartsWith(root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("API-Weiterleitung verlässt den API-Pfad. Reverse Proxy und Server-URL prüfen.");
        return target;
    }
    public async Task<string> RequestAsync(string path, HttpMethod method, string? body = null, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(Token)) throw new InvalidOperationException("API-Token fehlt.");
        var original = GetUri(path);
        var current = original;
        using var client = CreateClient();
        for (var redirects = 0; redirects <= 5; redirects++)
        {
            using var request = new HttpRequestMessage(method, current);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", Token.Trim());
            request.Headers.Accept.ParseAdd("application/json");
            request.Headers.UserAgent.ParseAdd("SemaphoreTenantConfigurator/2.0");
            if (body is not null) request.Content = new StringContent(body, Encoding.UTF8, "application/json");
            using var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
            LastDiagnostic = $"HTTP {(int)response.StatusCode} · {current.AbsolutePath} · {response.Content.Headers.ContentType?.MediaType ?? "kein Content-Type"}";
            if ((int)response.StatusCode is 301 or 302 or 303 or 307 or 308)
            {
                if (method != HttpMethod.Get) throw new InvalidOperationException(LastDiagnostic + " · POST wird niemals automatisch wiederholt.");
                if (response.Headers.Location is null) throw new InvalidOperationException(LastDiagnostic + " · Location fehlt.");
                current = GetSafeRedirect(current, original, new Uri(current, response.Headers.Location));
                continue;
            }
            if (response.StatusCode == HttpStatusCode.ProxyAuthenticationRequired) throw new InvalidOperationException("HTTP 407: Proxy-Anmeldung erforderlich. Windows-Anmeldung versuchen oder manuellen Proxy korrekt eintragen.");
            if (response.StatusCode == HttpStatusCode.Unauthorized) throw new InvalidOperationException("HTTP 401: Semaphore-API-Token ist ungültig oder abgelaufen.");
            if (!response.IsSuccessStatusCode) throw new InvalidOperationException(LastDiagnostic + " · API-Anfrage fehlgeschlagen.");
            var text = await response.Content.ReadAsStringAsync(ct);
            if (text.TrimStart().StartsWith('<')) throw new InvalidOperationException(LastDiagnostic + " · HTML statt JSON: Reverse Proxy oder Login-Redirect prüfen.");
            return text;
        }
        throw new InvalidOperationException("Zu viele API-Weiterleitungen (maximal 5).");
    }
    public async Task<List<ServerProject>> ListProjectsAsync(CancellationToken ct = default)
        => ParseProjectList(await RequestAsync("projects", HttpMethod.Get, ct: ct));
    // Eigener Parser für API-Projektlisten: niemals Backup-Konvertierung oder
    // ein implizites PowerShell-Pipeline-Array verwenden (v1.4-Regression).
    public static List<ServerProject> ParseProjectList(string raw)
    {
        JsonNode? node;
        try { node = JsonNode.Parse(raw); }
        catch (Exception ex) when (ex is System.Text.Json.JsonException) { throw new InvalidOperationException("/api/projects: Ungültiges JSON.", ex); }
        if (node is JsonObject envelope)
            node = envelope["projects"] ?? envelope["data"] ?? throw new InvalidOperationException("/api/projects: Antwort ist keine Projektliste.");
        var list = new List<ServerProject>();
        static void Add(JsonNode? n, List<ServerProject> dest)
        {
            if (n is JsonArray array) { foreach (var item in array) Add(item, dest); return; }
            if (n is not JsonObject obj || !int.TryParse(obj["id"]?.ToString(), out int id) || string.IsNullOrWhiteSpace(obj["name"]?.ToString()))
                throw new InvalidOperationException("/api/projects: Eintrag ohne id/name. Keine stillschweigende leere Liste.");
            dest.Add(new ServerProject(id, obj["name"]!.ToString()));
        }
        Add(node, list);
        return list;
    }
    public async Task<JsonObject> BackupAsync(int projectId, CancellationToken ct = default)
        => ProjectDocument.ParseBackup(await RequestAsync($"project/{projectId}/backup", HttpMethod.Get, ct: ct));
    public async Task<string> RestoreAsync(JsonObject backup, CancellationToken ct = default)
        => await RequestAsync("projects/restore", HttpMethod.Post, backup.ToJsonString(), ct);
}
