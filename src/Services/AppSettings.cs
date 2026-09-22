using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace SemaphoreTenantConfigurator.Services;

public sealed class AppSettings
{
    public string Url { get; set; } = "";
    public string ProxyMode { get; set; } = "Windows-Anmeldung";
    public string ProxyUrl { get; set; } = "";
    public bool SaveToken { get; set; }
    public static string Root => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SemaphoreProjectManager");
    private static string ConfigPath => Path.Combine(Root, "settings.json");
    private static string SecretPath => Path.Combine(Root, "credentials.dat");
    public static (AppSettings Settings, string Token) Load()
    {
        Directory.CreateDirectory(Root);
        var result = new AppSettings();
        try
        {
            if (File.Exists(ConfigPath))
            {
                using var json = JsonDocument.Parse(File.ReadAllText(ConfigPath));
                var root = json.RootElement;
                if (root.TryGetProperty("url", out var v)) result.Url = v.GetString() ?? "";
                if (root.TryGetProperty("proxy_mode", out v)) result.ProxyMode = v.GetString() ?? "Windows-Anmeldung";
                if (root.TryGetProperty("proxy_url", out v)) result.ProxyUrl = v.GetString() ?? "";
                if (root.TryGetProperty("save_token", out v)) result.SaveToken = v.ValueKind == JsonValueKind.True;
            }
        }
        catch (JsonException) { /* Beschädigte Einstellungen verhindern den Start nicht. */ }
        string token = "";
        if (result.SaveToken && File.Exists(SecretPath))
        {
            try { token = Encoding.UTF8.GetString(ProtectedData.Unprotect(Convert.FromBase64String(File.ReadAllText(SecretPath).Trim()), null, DataProtectionScope.CurrentUser)); }
            catch (CryptographicException) { /* anderes Windows-Konto oder Gerät */ }
            catch (FormatException) { /* Datei beschädigt */ }
        }
        return (result, token);
    }
    public void Save(string token)
    {
        Directory.CreateDirectory(Root);
        var json = JsonSerializer.Serialize(new { url = Url, proxy_mode = ProxyMode, proxy_url = ProxyUrl, save_token = SaveToken }, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(ConfigPath, json);
        if (SaveToken && !string.IsNullOrWhiteSpace(token))
        {
            var bytes = Encoding.UTF8.GetBytes(token);
            try { File.WriteAllText(SecretPath, Convert.ToBase64String(ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser))); }
            finally { CryptographicOperations.ZeroMemory(bytes); }
        }
        else if (File.Exists(SecretPath)) File.Delete(SecretPath);
    }
}
