; DrawTemp 5.5 R23.D — real per-user Windows preview installer.
; The installer's Authenticode signature is NOT supplied by this repository.
; All paths are provided by the trusted CI build invoking ISCC.
#ifndef SourceDir
  #error SourceDir required
#endif
#ifndef OutputDir
  #error OutputDir required
#endif

[Setup]
AppId=DrawTemp.Studio.5.5.Preview
AppName=DrawTemp Studio 5.5 Preview
AppVersion=5.5.0-preview.1
AppPublisher=DrawTemp Contributors
DefaultDirName={localappdata}\Programs\DrawTempStudio55Preview
DisableProgramGroupPage=yes
UninstallDisplayName=DrawTemp Studio 5.5 Preview
OutputDir={#OutputDir}
OutputBaseFilename=DrawTempStudio-5.5-preview-Windows
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableWelcomePage=no
ChangesAssociations=no
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

[Files]
Source: "{#SourceDir}\Jeanne\*"; DestDir: "{app}\Jeanne"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\Studio\*"; DestDir: "{app}\Studio"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\release.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\DrawTemp Studio 5.5 Preview"; Filename: "{app}\Studio\DrawTempStudio.exe"
Name: "{autoprograms}\DrawTemp Player - Jeanne"; Filename: "{app}\Jeanne\Player\DrawTempPlayer.exe"

[Run]
; Deliberately no post-install auto-launch or network fetches.
