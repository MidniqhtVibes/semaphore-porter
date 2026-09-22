using System.IO;
using Microsoft.Win32;
using SemaphoreTenantConfigurator.Services;
using System.Collections.ObjectModel;
using System.Globalization;
using System.Net;
using System.Runtime.InteropServices;
using System.Windows.Interop;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace SemaphoreTenantConfigurator;
public sealed record WizardStep(string Title, string Description);
public sealed record GroupItem(string Name, JsonObject Group);
public partial class MainWindow : Window
{
    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);
    private void EnableDarkTitleBar()
    {
        try
        {
            var handle = new WindowInteropHelper(this).Handle;
            int dark = 1;
            if (DwmSetWindowAttribute(handle, 20, ref dark, sizeof(int)) != 0)
                DwmSetWindowAttribute(handle, 19, ref dark, sizeof(int));
        }
        catch (DllNotFoundException) { } // Unsupported Windows version
        catch (EntryPointNotFoundException) { }
    }
    private static readonly WizardStep[] Steps =
    {
        new("01  Verbindung", "Server und Token"),
        new("02  Vorlage", "Projekt auswählen"),
        new("03  Tenant", "Kennung und Anwendung"),
        new("04  Inhalte", "Tasks und Gruppen"),
        new("05  Presets", "Variablen bearbeiten"),
        new("06  Prüfen", "Vorschau und Import"),
        new("07  Fertig", "Manuelle Nacharbeiten")
    };
    private static readonly string[] Help =
    {
        "Verbinde den Windows-Konfigurator mit deiner Semaphore-Instanz. Der Bearer-Token ist NICHT dein Proxy-Passwort. Im Modus Windows-Anmeldung werden die aktuellen Windows-Anmeldedaten für den Windows-Systemproxy verwendet. Für eine lokale Backup-Datei kannst du auch offline weiterarbeiten.",
        "Wähle ein Serverprojekt oder öffne eine lokale JSON-Backup-Datei. Aus dem Server wird GET /api/project/{id}/backup geladen. Der Wizard arbeitet anschließend nur auf einer lokalen Kopie. Das bestehende Projekt wird nicht überschrieben.",
        "Die technische Tenant-ID sollte zum Playbook passen: Kleinbuchstaben, Zahlen und Bindestriche. Werte wie application_id, database_type und dataset_id werden nur vorhandenen Surveys zugewiesen. Wähle daher gültige Optionen aus der Vorlage. Die Konfiguration startet noch kein Deployment.",
        "Übernimm nur erforderliche Task Templates und Variablengruppen. Entfernte Einträge fehlen ausschließlich in der neuen Kopie. Du kannst Git-URL/Branch des ersten Repositories übersteuern. Neue Tenant-Defaults werden als Gruppe angelegt und ausgewählten Tasks zugeordnet.",
        "Presets sind wiederverwendbare Variablengruppen ohne Geheimnisse. Du kannst eingebaute Presets oder eigene v1.6-Presets verwenden. Nach dem Hinzufügen kannst du einzelne Werte bearbeiten. Typen: Text, Zahl, Bool, JSON; komplexe Werte bei JSON als korrektes JSON eingeben.",
        "Vor dem POST /api/projects/restore wird eine Vorschau der neuen Konfiguration erzeugt und geprüft. Du kannst das JSON vorab lokal speichern. Der Import verlangt eine bewusste Bestätigung. Der Quellserver wird nicht für Test-Deployments genutzt, bevor du diese im neuen Projekt selbst startest.",
        "Das neue Semaphore-Projekt wurde erstellt. Kontrolliere Keys/Secrets, Inventory und Repository. Starte danach manuell ein Deployment und prüfe tenant_slug sowie den gewünschten Datensatz. Das Restore ist kein automatischer Testcontainer-Start."
    };
    private readonly SemaphoreApi _api = new();
    private readonly ObservableCollection<ServerProject> _projects = new();
    private readonly ObservableCollection<ResourceChoice> _tasks = new();
    private readonly ObservableCollection<ResourceChoice> _groups = new();
    private readonly ObservableCollection<ValueRow> _values = new();
    private readonly ObservableCollection<GroupPreset> _presets = new();
    private ProjectDocument? _document;
    private JsonObject? _prepared;
    private JsonObject? _editingGroup;
    private GroupItem? _editingGroupItem;
    private bool _loadingGroup;
    private int _step;
    private int _furthest;
    private bool _busy;
    private string _sourceLabel = "Noch keine Quelle";
    private List<ServerProject> _allProjects = new();
    public MainWindow()
    {
        InitializeComponent();
        SourceInitialized += (_, _) => EnableDarkTitleBar();
        StepsList.ItemsSource = Steps;
        ProjectList.ItemsSource = _projects;
        TasksChoiceList.ItemsSource = _tasks;
        GroupsChoiceList.ItemsSource = _groups;
        ValuesGrid.ItemsSource = _values;
        PresetBox.ItemsSource = _presets;
        var (settings, token) = AppSettings.Load();
        ServerBox.Text = settings.Url;
        TokenBox.Password = token;
        SaveTokenCheck.IsChecked = settings.SaveToken;
        ProxyUrlBox.Text = settings.ProxyUrl;
        foreach (ComboBoxItem item in ProxyModeBox.Items)
            if ((string)item.Content == settings.ProxyMode) { ProxyModeBox.SelectedItem = item; break; }
        if (ProxyModeBox.SelectedIndex < 0) ProxyModeBox.SelectedIndex = 0;
        TtlBox.Text = "15";
        RenderStep();
    }
    private void Status(string message, bool success = false)
    {
        FooterStatus.Text = message;
        StatusLabel.Text = success ? "Verbunden" : "Bereit";
        StatusDot.Fill = (SolidColorBrush)FindResource(success ? "Positive" : "Muted");
        FooterDiagnostic.Text = _api.LastDiagnostic;
    }
    private void Error(Exception ex)
    {
        Status(ex.Message);
        MessageBox.Show(this, ex.Message, "Semaphore Tenant Configurator", MessageBoxButton.OK, MessageBoxImage.Warning);
    }
    private void SetBusy(bool state, string message = "")
    {
        _busy = state;
        NextButton.IsEnabled = !state;
        BackButton.IsEnabled = !state && _step > 0;
        if (message.Length > 0) Status(message);
        Cursor = state ? System.Windows.Input.Cursors.Wait : System.Windows.Input.Cursors.Arrow;
    }
    private void ApplyConnection()
    {
        _api.BaseUrl = ServerBox.Text.Trim();
        _api.Token = TokenBox.Password;
        _api.ProxyMode = (ProxyModeBox.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "Windows-Anmeldung";
        _api.ProxyUrl = ProxyUrlBox.Text.Trim();
        _api.ManualCredential = _api.ProxyMode == "Manuell" && ProxyUserBox.Text.Length > 0
            ? new NetworkCredential(ProxyUserBox.Text, ProxyPasswordBox.Password) : null;
    }
    private void SaveSettings()
    {
        ApplyConnection();
        new AppSettings { Url = _api.BaseUrl, ProxyMode = _api.ProxyMode, ProxyUrl = _api.ProxyUrl,
            SaveToken = SaveTokenCheck.IsChecked == true }.Save(_api.Token);
    }
    private void SaveConnection_Click(object sender, RoutedEventArgs e)
    {
        try { SaveSettings(); Status("Verbindungseinstellungen gespeichert. Token nur bei aktiviertem Haken verschlüsselt abgelegt."); }
        catch (Exception ex) { Error(ex); }
    }
    private void ProxyMode_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (ProxyUrlBox is null) return;
        bool manual = (ProxyModeBox.SelectedItem as ComboBoxItem)?.Content?.ToString() == "Manuell";
        ProxyUrlBox.IsEnabled = manual;
        ProxyUserBox.IsEnabled = manual;
        ProxyPasswordBox.IsEnabled = manual;
    }
    private async void Connect_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        try
        {
            ApplyConnection();
            SetBusy(true, "Server-Projektliste wird geladen …");
            var items = await _api.ListProjectsAsync();
            _allProjects = items;
            FilterProjects();
            ConnectionInfo.Text = $"✓ {_allProjects.Count} Projekte geladen. {_api.LastDiagnostic}";
            try { SaveSettings(); } catch (Exception ex) { ConnectionInfo.Text += $"\nHinweis: Einstellungen konnten nicht gespeichert werden: {ex.Message}"; }
            Status($"{_allProjects.Count} Projekte geladen. Quelle auswählen.", true);
            if (_step == 0) Navigate(1);
        }
        catch (Exception ex) { Error(ex); ConnectionInfo.Text = ex.Message; }
        finally { SetBusy(false); }
    }
    private void SourceFilter_Changed(object sender, TextChangedEventArgs e) => FilterProjects();
    private void FilterProjects()
    {
        if (SourceFilter is null) return;
        var term = SourceFilter.Text.Trim();
        _projects.Clear();
        foreach (var project in _allProjects.Where(p => term.Length == 0 || p.Name.Contains(term, StringComparison.OrdinalIgnoreCase) || p.Id.ToString().Contains(term)))
            _projects.Add(project);
    }
    private async void ProjectList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ProjectList.SelectedItem is not ServerProject project || _busy) return;
        try
        {
            ApplyConnection(); SetBusy(true, $"Backup für Projekt #{project.Id} wird geladen …");
            var backup = await _api.BackupAsync(project.Id);
            LoadBackup(backup, project.Display);
            Status($"Vorlage '{project.Name}' geladen.", true);
        }
        catch (Exception ex) { Error(ex); }
        finally { SetBusy(false); }
    }
    private void OpenBackup_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFileDialog { Filter = "Semaphore-Backup (*.json;*.backup)|*.json;*.backup|Alle Dateien (*.*)|*.*" };
            if (dialog.ShowDialog(this) != true) return;
            LoadBackup(ProjectDocument.ParseBackup(File.ReadAllText(dialog.FileName)), dialog.FileName);
            Navigate(2);
            Status("Lokale Vorlage geladen. Offline-Bearbeitung möglich.");
        }
        catch (Exception ex) { Error(ex); }
    }
    private void LoadBackup(JsonObject source, string label)
    {
        _document = new ProjectDocument(source);
        _sourceLabel = label;
        _prepared = null;
        _tasks.Clear(); _groups.Clear();
        foreach (var template in ProjectDocument.List(_document.Working, "templates").OfType<JsonObject>())
            _tasks.Add(new ResourceChoice { Name = template["name"]?.ToString() ?? "Unbenannt" });
        foreach (var group in ProjectDocument.List(_document.Working, "environments").OfType<JsonObject>())
            _groups.Add(new ResourceChoice { Name = group["name"]?.ToString() ?? "Unbenannt" });
        ProjectNameBox.Text = (_document.SourceName + "-tenant");
        TenantSlugBox.Text = "";
        var firstRepo = ProjectDocument.List(_document.Working, "repositories").OfType<JsonObject>().FirstOrDefault();
        RepositoryUrlBox.Text = firstRepo?["git_url"]?.ToString() ?? "";
        RepositoryBranchBox.Text = firstRepo?["git_branch"]?.ToString() ?? "";
        SetComboOptions(ApplicationBox, "application_id");
        SetComboOptions(DatabaseBox, "database_type");
        SetComboOptions(DatasetBox, "dataset_id");
        TtlBox.Text = "15";
        RefreshGroupCombo();
        ReloadPresets();
        SourceInfo.Text = $"Ausgewählt: {_document.SourceName}\nTasks: {_tasks.Count} · Variablengruppen: {_groups.Count}";
        Summary_Changed(this, new TextChangedEventArgs(TextBox.TextChangedEvent, UndoAction.None));
    }
    private void SetComboOptions(ComboBox box, string key)
    {
        box.Items.Clear(); box.Text = "";
        if (_document is null) return;
        foreach (var option in ProjectDocument.SurveyOptions(_document.Working, key)) box.Items.Add(option);
        // Kein erfundener Standardwert: Benutzer wählt bewusst die passende Variante.
    }
    private WizardChoices GetChoices() => new()
    {
        ProjectName = ProjectNameBox.Text,
        TenantSlug = TenantSlugBox.Text,
        ApplicationId = ApplicationBox.Text.Trim(),
        DatabaseType = DatabaseBox.Text.Trim(),
        DatasetId = DatasetBox.Text.Trim(),
        TtlMinutes = TtlBox.Text.Trim(),
        AddTenantGroup = AddTenantGroupCheck.IsChecked == true,
        AddTenantSurvey = AddTenantSurveyCheck.IsChecked == true,
        DisableSchedules = DisableSchedulesCheck.IsChecked == true,
        DisableIntegrations = DisableIntegrationsCheck.IsChecked == true,
        RepositoryUrl = RepositoryUrlBox.Text.Trim(),
        RepositoryBranch = RepositoryBranchBox.Text.Trim()
    };
    private static JsonNode? ParseValue(ValueRow row)
    {
        return row.Type.Trim().ToLowerInvariant() switch
        {
            "zahl" or "number" or "int" => decimal.TryParse(row.Value, NumberStyles.Any, CultureInfo.InvariantCulture, out var number) ? JsonValue.Create(number) : throw new InvalidOperationException($"'{row.Key}': ungültige Zahl (Punkt als Dezimalzeichen verwenden)."),
            "bool" or "boolean" => bool.TryParse(row.Value, out var flag) ? JsonValue.Create(flag) : throw new InvalidOperationException($"'{row.Key}': Bool muss true oder false sein."),
            "json" => JsonNode.Parse(row.Value),
            "text" or "string" or "" => JsonValue.Create(row.Value),
            _ => throw new InvalidOperationException($"'{row.Key}': ungültiger Typ. Verwende Text, Zahl, Bool oder JSON.")
        };
    }
    private void SaveEditingGroup()
    {
        if (_editingGroup is null || _loadingGroup) return;
        ValuesGrid.CommitEdit(DataGridEditingUnit.Cell, true);
        ValuesGrid.CommitEdit(DataGridEditingUnit.Row, true);
        var obj = new JsonObject();
        foreach (var row in _values)
        {
            var key = row.Key.Trim();
            if (key.Length == 0) throw new InvalidOperationException("Eine Variablenzeile hat keinen Namen.");
            if (obj.ContainsKey(key)) throw new InvalidOperationException($"Variable '{key}' ist doppelt.");
            obj[key] = ParseValue(row);
        }
        ProjectDocument.SetGroupValues(_editingGroup, obj);
    }
    private void EditableGroup_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_loadingGroup) return;
        try
        {
            SaveEditingGroup();
            _editingGroupItem = EditableGroupBox.SelectedItem as GroupItem;
            _editingGroup = _editingGroupItem?.Group;
            _values.Clear();
            if (_editingGroup is null) return;
            var obj = ProjectDocument.ParseGroupValues(_editingGroup);
            foreach (var entry in obj)
            {
                var type = entry.Value switch
                {
                    JsonObject or JsonArray => "JSON",
                    JsonValue v when v.TryGetValue<bool>(out _) => "Bool",
                    JsonValue v when v.TryGetValue<string>(out _) => "Text",
                    _ => "Zahl"
                };
                var value = type == "Text" ? entry.Value?.ToString() ?? "" : type == "JSON" ? entry.Value?.ToJsonString() ?? "null" : entry.Value?.ToString() ?? "";
                _values.Add(new ValueRow { Key = entry.Key, Value = value, Type = type });
            }
        }
        catch (Exception ex) { Error(ex); }
    }
    private void RefreshGroupCombo()
    {
        if (_document is null) return;
        _loadingGroup = true;
        var prior = _editingGroup?["name"]?.ToString();
        var all = ProjectDocument.List(_document.Working, "environments").OfType<JsonObject>()
            .Select(group => new GroupItem(group["name"]?.ToString() ?? "", group)).ToList();
        EditableGroupBox.ItemsSource = all;
        _editingGroup = null;
        _values.Clear();
        _loadingGroup = false;
        if (all.Count > 0) EditableGroupBox.SelectedItem = all.FirstOrDefault(g => g.Name == prior) ?? all[0];
    }
    private void ReloadPresets()
    {
        _presets.Clear(); foreach (var preset in Presets.All()) _presets.Add(preset);
        if (_presets.Count > 0) PresetBox.SelectedIndex = 0;
    }
    private void PresetBox_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (PresetBox.SelectedItem is not GroupPreset preset) return;
        PresetDescription.Text = preset.Description;
        PresetNameBox.Text = preset.Group["name"]?.ToString() ?? "";
    }
    private void AddPreset_Click(object sender, RoutedEventArgs e)
    {
        if (_document is null || PresetBox.SelectedItem is not GroupPreset preset) return;
        try
        {
            SaveEditingGroup();
            var clone = (JsonObject)preset.Group.DeepClone();
            clone["name"] = ProjectDocument.NextName(_document.Working, "environments", string.IsNullOrWhiteSpace(PresetNameBox.Text) ? "Neue-Gruppe" : PresetNameBox.Text.Trim());
            // Sicherstellen, dass das Preset nicht bereits vor dem Import fehlerhaft ist.
            ProjectDocument.ParseGroupValues(clone);
            if (_document.Working["environments"] is not JsonArray all) { all = new JsonArray(); _document.Working["environments"] = all; }
            all.Add(clone);
            _groups.Add(new ResourceChoice { Name = clone["name"]!.ToString(), Included = true });
            RefreshGroupCombo();
            EditableGroupBox.SelectedItem = ((IEnumerable<GroupItem>)EditableGroupBox.ItemsSource).FirstOrDefault(g => ReferenceEquals(g.Group, clone));
            Status($"Gruppe '{clone["name"]}' ergänzt.");
        }
        catch (Exception ex) { Error(ex); }
    }
    private void AddValue_Click(object sender, RoutedEventArgs e) => _values.Add(new ValueRow { Key = "neue_variable", Value = "", Type = "Text" });
    private void RemoveValue_Click(object sender, RoutedEventArgs e)
    {
        if (ValuesGrid.SelectedItem is ValueRow row) _values.Remove(row);
    }
    private void SaveGroup_Click(object sender, RoutedEventArgs e)
    {
        try { SaveEditingGroup(); Status("Variablengruppe übernommen."); }
        catch (Exception ex) { Error(ex); }
    }
    private void SavePreset_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SaveEditingGroup();
            if (_editingGroup is null) throw new InvalidOperationException("Bitte zuerst eine Gruppe auswählen.");
            var title = _editingGroup["name"]?.ToString() ?? "";
            if (MessageBox.Show(this, $"Gruppe '{title}' als eigene Vorlage speichern?\nKeine Zugangsdaten übernehmen!", "Preset speichern", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
            Presets.SaveCustom(_editingGroup, title, "Aus dem Tenant-Konfigurator gespeichert");
            ReloadPresets(); Status("Preset im Benutzerprofil gespeichert.");
        }
        catch (Exception ex) { Error(ex); }
    }
    private JsonObject BuildPreview()
    {
        if (_document is null) throw new InvalidOperationException("Bitte zuerst eine Projektquelle auswählen.");
        SaveEditingGroup();
        var choices = GetChoices();
        if (string.IsNullOrWhiteSpace(choices.ProjectName)) throw new InvalidOperationException("Neuer Projektname fehlt.");
        if (!ProjectDocument.ValidTenantSlug(choices.TenantSlug)) throw new InvalidOperationException("Tenant-ID: 2–31 Zeichen, klein geschrieben, nur a-z, 0-9 und Bindestrich; kein Bindestrich am Ende.");
        if (!int.TryParse(choices.TtlMinutes, out var ttl) || ttl < 5 || ttl > 1440) throw new InvalidOperationException("TTL muss zwischen 5 und 1440 Minuten liegen.");
        if (_tasks.All(x => !x.Included)) throw new InvalidOperationException("Mindestens ein Task Template muss ausgewählt werden.");
        // Falls die Auswahl bewusst eine Variablengruppe entfernt, müssen ihre Task-Referenzen angepasst werden.
        return ProjectDocument.Prepare(_document.Working, choices, _tasks, _groups);
    }
    private void Review()
    {
        _prepared = BuildPreview();
        var (errors, warnings) = ProjectDocument.Validate(_prepared);
        var name = _prepared["meta"]?["name"]?.ToString() ?? "?";
        PreviewBox.Text = $"QUELLE: {_sourceLabel}\nNEUES PROJEKT: {name}\nTENANT-ID: {TenantSlugBox.Text}\nANWENDUNG: {ApplicationBox.Text}\nDATENBANK: {DatabaseBox.Text}\nDATENSATZ: {DatasetBox.Text}\n\nTASKS: {ProjectDocument.List(_prepared, "templates").Count}\nGRUPPEN: {ProjectDocument.List(_prepared, "environments").Count}\nREPOSITORIES: {ProjectDocument.List(_prepared, "repositories").Count}\nINVENTORIES: {ProjectDocument.List(_prepared, "inventories").Count}\nKEY-REFERENZEN: {ProjectDocument.List(_prepared, "keys").Count}\nZEITPLÄNE: {ProjectDocument.List(_prepared, "schedules").Count}\nINTEGRATIONEN: {ProjectDocument.List(_prepared, "integrations").Count}";
        if (_allProjects.Any(p => string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase))) warnings.Insert(0, "Ein Serverprojekt mit diesem Namen existiert bereits. Restore erzeugt ein weiteres Projekt: Projektname ändern.");
        WarningsBox.Text = (errors.Count == 0 ? "✓ Strukturprüfung bestanden" : "FEHLER:\n" + string.Join("\n", errors)) + "\n\nHINWEISE:\n" + (warnings.Count == 0 ? "Keine weiteren lokalen Warnungen." : string.Join("\n", warnings));
        RestoreButton.IsEnabled = errors.Count == 0;
        if (errors.Count > 0) Status($"Prüfung: {errors.Count} Fehler; Import gesperrt.");
        else Status("Vorschau erstellt. Vor Import Hinweise und Keys kontrollieren.");
    }
    private void Review_Click(object sender, RoutedEventArgs e)
    {
        try { Review(); }
        catch (Exception ex) { Error(ex); }
    }
    private void SavePreview_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Review();
            if (_prepared is null) return;
            var dialog = new SaveFileDialog { FileName = "semaphore-tenant-" + TenantSlugBox.Text + ".json", Filter = "JSON-Backup (*.json)|*.json" };
            if (dialog.ShowDialog(this) == true) { File.WriteAllText(dialog.FileName, _prepared.ToJsonString(new JsonSerializerOptions { WriteIndented = true })); Status("Vorschau als JSON gespeichert."); }
        }
        catch (Exception ex) { Error(ex); }
    }
    private async void Restore_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        try
        {
            Review();
            if (_prepared is null || RestoreButton.IsEnabled == false) return;
            if (ConfirmCheck.IsChecked != true) throw new InvalidOperationException("Bestätigung vor dem Import fehlt.");
            if (_allProjects.Any(p => string.Equals(p.Name, ProjectNameBox.Text, StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("Projektname bereits vorhanden. Für eine neue Kopie bitte einen eindeutigen Namen verwenden.");
            if (MessageBox.Show(this, $"JETZT neues Projekt '{ProjectNameBox.Text}' auf '{ServerBox.Text}' erstellen?\n\nDas Quellprojekt bleibt erhalten. Ein Ansible-Task wird NICHT gestartet.", "Import endgültig bestätigen", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
            ApplyConnection();
            SetBusy(true, "Semaphore-Restore wird gesendet …");
            var response = await _api.RestoreAsync(_prepared);
            ResultInfo.Text = $"Semaphore hat den Restore für '{ProjectNameBox.Text}' angenommen.\n\nAntwort: {response[..Math.Min(response.Length, 500)]}";
            _furthest = 6;
            Navigate(6);
            Status("Restore-Anfrage erfolgreich. Keys und Deployment prüfen.", true);
        }
        catch (Exception ex) { Error(ex); }
        finally { SetBusy(false); }
    }
    private void Restart_Click(object sender, RoutedEventArgs e)
    {
        _prepared = null; ConfirmCheck.IsChecked = false; _furthest = 1; Navigate(1);
    }
    private void Summary_Changed(object sender, TextChangedEventArgs e)
    {
        if (SummaryText is null) return;
        SummaryText.Text = $"Quelle:\n{_sourceLabel}\n\nNeues Projekt:\n{ProjectNameBox?.Text}\n\nTenant:\n{TenantSlugBox?.Text}\n\nTasks: {_tasks.Count(t => t.Included)}\nGruppen: {_groups.Count(g => g.Included)}";
    }
    private void StepsList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (StepsList?.SelectedIndex is int n && n >= 0 && n <= _furthest && n != _step && !_busy) Navigate(n);
        else if (StepsList is not null && StepsList.SelectedIndex != _step) StepsList.SelectedIndex = _step;
    }
    private void Navigate(int step)
    {
        _step = step;
        _furthest = Math.Max(_furthest, step);
        RenderStep();
    }
    private void RenderStep()
    {
        if (StepsList is null) return;
        var pages = new[] { PageConnection, PageSource, PageTenant, PageResources, PageGroups, PageReview, PageResult };
        for (var i = 0; i < pages.Length; i++) pages[i].Visibility = i == _step ? Visibility.Visible : Visibility.Collapsed;
        StepsList.SelectedIndex = _step;
        PageTitle.Text = Steps[_step].Title[4..];
        PageSubtitle.Text = Steps[_step].Description;
        HelpTitle.Text = Steps[_step].Title;
        HelpBody.Text = Help[_step];
        BackButton.IsEnabled = _step > 0;
        BackButton.Visibility = _step == 6 ? Visibility.Collapsed : Visibility.Visible;
        NextButton.Visibility = _step >= 5 ? Visibility.Collapsed : Visibility.Visible;
        NextButton.Content = _step == 0 ? "Vorlage wählen →" : "Weiter →";
        Summary_Changed(this, new TextChangedEventArgs(TextBox.TextChangedEvent, UndoAction.None));
        if (_step == 5) try { Review(); } catch (Exception ex) { Status(ex.Message); RestoreButton.IsEnabled = false; WarningsBox.Text = ex.Message; }
    }
    private void Back_Click(object sender, RoutedEventArgs e)
    {
        if (_step > 0) Navigate(_step - 1);
    }
    private void Next_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        try
        {
            if (_step == 1 && _document is null) throw new InvalidOperationException("Bitte zuerst ein Serverprojekt oder eine JSON-Datei auswählen.");
            if (_step == 2) { BuildPreview(); }
            if (_step == 4) SaveEditingGroup();
            if (_step < 5) Navigate(_step + 1);
        }
        catch (Exception ex) { Error(ex); }
    }
    private void Help_Click(object sender, RoutedEventArgs e)
        => MessageBox.Show(this, Help[_step], "Hilfe · " + Steps[_step].Title, MessageBoxButton.OK, MessageBoxImage.Information);
}
