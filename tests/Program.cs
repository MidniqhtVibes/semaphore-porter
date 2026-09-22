using SemaphoreTenantConfigurator.Services;
using System.Text.Json.Nodes;

static void Require(bool pass, string message)
{
    if (!pass) throw new Exception("TEST FEHLGESCHLAGEN: " + message);
    Console.WriteLine("PASS: " + message);
}
var source = ProjectDocument.ParseBackup("""
{"meta":{"name":"Demo","alert":false},"templates":[{"name":"Deploy","repository":"Git","inventory":"Local","environments":["Defaults"],"survey_vars":[{"name":"tenant_slug","title":"Tenant","type":"","default_value":"old","values":[]},{"name":"application_id","type":"enum","default_value":"app","values":[{"name":"App","value":"app"}]}]}],"environments":[{"name":"Defaults","json":"{\"x\":1}","env":"{}"}],"repositories":[{"name":"Git","git_url":"https://git.invalid/repo","git_branch":"main"}],"inventories":[{"name":"Local","inventory":"inventory.ini","type":"file"}],"keys":[],"schedules":[{"name":"auto"}],"integrations":[{"name":"webhook"}]}
""");
Require(ProjectDocument.ValidTenantSlug("kunde-a"), "Tenant-ID gültig");
Require(!ProjectDocument.ValidTenantSlug("Kunde_A"), "Tenant-ID ungültig abgefangen");
Require(ProjectDocument.SurveyOptions(source, "application_id").SequenceEqual(new[] { "app" }), "Survey-Optionen");
var plan = new WizardChoices { ProjectName = "Demo-Kunde-A", TenantSlug = "kunde-a", ApplicationId = "app" };
var result = ProjectDocument.Prepare(source, plan, new[] { new ResourceChoice { Name = "Deploy" } }, new[] { new ResourceChoice { Name = "Defaults" } });
Require(result["meta"]?["name"]?.ToString() == "Demo-Kunde-A", "Projektname");
Require(source["meta"]?["name"]?.ToString() == "Demo", "Quellprojekt unverändert");
Require(ProjectDocument.List(result, "schedules").Count == 0, "Zeitpläne deaktiviert");
Require(ProjectDocument.List(result, "integrations").Count == 0, "Integrationen deaktiviert");
Require(ProjectDocument.List(result, "environments").Count == 2, "Tenant-Gruppe angelegt");
Require(ProjectDocument.List(result, "templates")[0]?["survey_vars"]?[0]?["default_value"]?.ToString() == "kunde-a", "tenant_slug aktualisiert");
Require(ProjectDocument.Validate(result).Errors.Count == 0, "Validierung erfolgreich");
Require(Presets.All().Count >= 8, "Presets verfügbar");
Require(SemaphoreApi.ParseProjectList("[]").Count == 0, "API: leere Projektliste");
Require(SemaphoreApi.ParseProjectList("[{\"id\":2,\"name\":\"Azubiorga-test\"}]").Single().Id == 2, "API: ein Projekt");
Require(SemaphoreApi.ParseProjectList("[{\"id\":2,\"name\":\"A\"},{\"id\":3,\"name\":\"B\"}]").Count == 2, "API: mehrere Projekte");
Require(SemaphoreApi.ParseProjectList("[[{\"id\":2,\"name\":\"A\"}],[{\"id\":3,\"name\":\"B\"}]]").Count == 2, "API: verschachtelte Listen");
Require(SemaphoreApi.ParseProjectList("{\"data\":[{\"id\":2,\"name\":\"A\"}]}").Single().Id == 2, "API: data-Umschlag");
Require(SemaphoreApi.ParseProjectList("{\"projects\":[{\"id\":2,\"name\":\"A\"}]}").Single().Id == 2, "API: projects-Umschlag");
foreach (string invalid in new[] { "{}", "[]", "null" })
{
    bool rejected = false;
    try { ProjectDocument.ParseBackup(invalid); }
    catch { rejected = true; }
    Require(rejected, "Ungültiges Backup abgelehnt: " + invalid);
}
Console.WriteLine("Alle Offline-Tests erfolgreich.");
