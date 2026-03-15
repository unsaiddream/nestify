; ============================================================
; Nestify — Windows Installer Script (NSIS + MUI2)
; ============================================================
!include "MUI2.nsh"
!include "FileFunc.nsh"

; ----- Метаданные -----
!define APP_NAME        "Nestify"
!define APP_VERSION     "1.0.0"
!define APP_PUBLISHER   "Nestify"
!define APP_EXE         "Nestify.exe"
!define REG_UNINSTALL   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

Name            "${APP_NAME}"
OutFile         "..\dist\Nestify-Setup.exe"
InstallDir      "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "Install_Dir"
RequestExecutionLevel admin
Unicode True

; ----- Настройки интерфейса -----
!define MUI_ABORTWARNING
!define MUI_ICON          "..\assets\logo.ico"
!define MUI_UNICON        "..\assets\logo.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP_NOSTRETCH

!define MUI_WELCOMEPAGE_TITLE   "Добро пожаловать в Nestify"
!define MUI_WELCOMEPAGE_TEXT    "Nestify — AI агент для риелторов на Krisha.kz.$\n$\nАвтоматизирует поиск объявлений и общение с продавцами.$\n$\nВ комплекте уже включён браузер Chromium — дополнительная установка не требуется."

!define MUI_FINISHPAGE_RUN          "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT     "Запустить Nestify"
!define MUI_FINISHPAGE_LINK         "Открыть папку установки"
!define MUI_FINISHPAGE_LINK_LOCATION "$INSTDIR"

; ----- Страницы установки -----
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; ----- Страницы удаления -----
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ----- Язык -----
!insertmacro MUI_LANGUAGE "Russian"

; ============================================================
; Установка
; ============================================================
Section "Nestify" SecMain
  SetOutPath "$INSTDIR"

  ; Копируем все файлы приложения (включая playwright-browsers/chromium)
  File /r "..\dist\Nestify\*.*"

  ; Ярлык в Start Menu
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Удалить ${APP_NAME}.lnk" \
    "$INSTDIR\Uninstall.exe"

  ; Ярлык на рабочем столе
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

  ; Регистрация в «Программы и компоненты»
  WriteRegStr HKLM "Software\${APP_NAME}" "Install_Dir" "$INSTDIR"
  WriteRegStr HKLM "${REG_UNINSTALL}" "DisplayName"     "${APP_NAME}"
  WriteRegStr HKLM "${REG_UNINSTALL}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${REG_UNINSTALL}" "DisplayIcon"     "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "${REG_UNINSTALL}" "Publisher"       "${APP_PUBLISHER}"
  WriteRegStr HKLM "${REG_UNINSTALL}" "DisplayVersion"  "${APP_VERSION}"
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoModify"  1
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoRepair"   1

  ; Размер установки
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ============================================================
; Удаление
; ============================================================
Section "Uninstall"
  ; Удаляем файлы
  RMDir /r "$INSTDIR"

  ; Ярлыки
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Удалить ${APP_NAME}.lnk"
  RMDir  "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"

  ; Реестр
  DeleteRegKey HKLM "${REG_UNINSTALL}"
  DeleteRegKey HKLM "Software\${APP_NAME}"
SectionEnd
