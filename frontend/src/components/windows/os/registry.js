// ─────────────────────────────────────────────────────────────────────────
// Registry seed. Stored as nested keys: { __values: [{name,type,data}], childKey: {...} }
// ─────────────────────────────────────────────────────────────────────────

const v = (name, type, data) => ({ name, type, data })

export const SEED_REGISTRY = {
  HKEY_CLASSES_ROOT: {
    __values: [v('(Default)', 'REG_SZ', '(value not set)')],
    '.txt': { __values: [v('(Default)', 'REG_SZ', 'txtfile'), v('Content Type', 'REG_SZ', 'text/plain')] },
    '.exe': { __values: [v('(Default)', 'REG_SZ', 'exefile'), v('Content Type', 'REG_SZ', 'application/x-msdownload')] },
    '.ps1': { __values: [v('(Default)', 'REG_SZ', 'Microsoft.PowerShellScript.1')] },
    txtfile: { __values: [v('(Default)', 'REG_SZ', 'Text Document')] },
  },
  HKEY_CURRENT_USER: {
    __values: [],
    Environment: { __values: [v('PATH', 'REG_EXPAND_SZ', '%USERPROFILE%\\AppData\\Local\\Microsoft\\WindowsApps'), v('TEMP', 'REG_EXPAND_SZ', '%USERPROFILE%\\AppData\\Local\\Temp'), v('TMP', 'REG_EXPAND_SZ', '%USERPROFILE%\\AppData\\Local\\Temp')] },
    'Control Panel': { __values: [], Desktop: { __values: [v('Wallpaper', 'REG_SZ', 'C:\\Windows\\Web\\Wallpaper\\Windows\\img0.jpg'), v('ScreenSaveActive', 'REG_SZ', '1'), v('ScreenSaveTimeOut', 'REG_SZ', '900')] } },
    Software: {
      __values: [],
      Microsoft: {
        __values: [],
        Windows: { __values: [], CurrentVersion: { __values: [], Run: { __values: [v('VMware User Process', 'REG_SZ', 'C:\\Program Files\\VMware\\VMware Tools\\vmtoolsd.exe -n vmusr')] }, Explorer: { __values: [v('ShellState', 'REG_BINARY', '24 00 00 00 38 28 00 00')] } } },
      },
    },
  },
  HKEY_LOCAL_MACHINE: {
    __values: [],
    HARDWARE: {
      __values: [],
      DESCRIPTION: { __values: [], System: { __values: [], CentralProcessor: { __values: [], 0: { __values: [v('ProcessorNameString', 'REG_SZ', 'Intel(R) Core(TM) i7-9700 CPU @ 3.00GHz'), v('VendorIdentifier', 'REG_SZ', 'GenuineIntel'), v('~MHz', 'REG_DWORD', '0x00000bb8 (3000)'), v('Identifier', 'REG_SZ', 'Intel64 Family 6 Model 158 Stepping 13')] } } } },
    },
    SAM: { __values: [], __denied: true },
    SECURITY: { __values: [], __denied: true },
    SOFTWARE: {
      __values: [],
      Microsoft: {
        __values: [],
        'Windows NT': {
          __values: [],
          CurrentVersion: {
            __values: [
              v('ProductName', 'REG_SZ', 'Windows Server 2022 Standard Evaluation'),
              v('EditionID', 'REG_SZ', 'ServerStandardEval'),
              v('ReleaseId', 'REG_SZ', '2009'),
              v('CurrentBuild', 'REG_SZ', '20348'),
              v('CurrentBuildNumber', 'REG_SZ', '20348'),
              v('UBR', 'REG_DWORD', '0x00000962 (2402)'),
              v('BuildLabEx', 'REG_SZ', '20348.2402.amd64fre.fe_release.210507-1500'),
              v('InstallationType', 'REG_SZ', 'Server'),
              v('RegisteredOwner', 'REG_SZ', 'Lab Industries'),
              v('InstallDate', 'REG_DWORD', '0x64db3a40'),
              v('SystemRoot', 'REG_SZ', 'C:\\Windows'),
            ],
          },
        },
        Windows: {
          __values: [],
          CurrentVersion: {
            __values: [],
            Run: { __values: [v('SecurityHealth', 'REG_EXPAND_SZ', '%windir%\\system32\\SecurityHealthSystray.exe'), v('VMware Tools', 'REG_SZ', '"C:\\Program Files\\VMware\\VMware Tools\\vmtoolsd.exe" -n vmusr')] },
            Policies: { __values: [], System: { __values: [v('EnableLUA', 'REG_DWORD', '0x00000001 (1)'), v('ConsentPromptBehaviorAdmin', 'REG_DWORD', '0x00000002 (2)'), v('PromptOnSecureDesktop', 'REG_DWORD', '0x00000001 (1)')] } },
            Uninstall: { __values: [] },
          },
        },
        PowerShell: { __values: [], 1: { __values: [], ShellIds: { __values: [], 'Microsoft.PowerShell': { __values: [v('Path', 'REG_SZ', 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe')] } } } },
      },
    },
    SYSTEM: {
      __values: [],
      ControlSet001: {
        __values: [],
        Control: {
          __values: [],
          ComputerName: { __values: [], ComputerName: { __values: [v('ComputerName', 'REG_SZ', 'SERVER01')] }, ActiveComputerName: { __values: [v('ComputerName', 'REG_SZ', 'SERVER01')] } },
          'Session Manager': { __values: [], Environment: { __values: [v('Path', 'REG_EXPAND_SZ', 'C:\\Windows\\system32;C:\\Windows;C:\\Windows\\System32\\Wbem;C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\'), v('NUMBER_OF_PROCESSORS', 'REG_SZ', '8'), v('OS', 'REG_SZ', 'Windows_NT'), v('PROCESSOR_ARCHITECTURE', 'REG_SZ', 'AMD64'), v('windir', 'REG_EXPAND_SZ', 'C:\\Windows')] } },
          TimeZoneInformation: { __values: [v('TimeZoneKeyName', 'REG_SZ', 'Eastern Standard Time'), v('StandardName', 'REG_SZ', 'Eastern Standard Time'), v('Bias', 'REG_DWORD', '0x0000012c (300)')] },
        },
        Services: { __values: [] },
      },
      CurrentControlSet: { __values: [], __link: 'ControlSet001' },
    },
  },
  HKEY_USERS: {
    __values: [],
    '.DEFAULT': { __values: [] },
    'S-1-5-21-1234567890-987654321-1122334455-500': { __values: [] },
  },
  HKEY_CURRENT_CONFIG: { __values: [], Software: { __values: [] }, System: { __values: [] } },
}
