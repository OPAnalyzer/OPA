"""Runtime Azerbaijani/English localization for the desktop interface.

The application historically embedded user-facing strings directly in the
widgets.  This module keeps English as the canonical source language and
translates the complete Qt widget tree without changing model data, combo-box
IDs, table values, or scientific calculations.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QWidget,
)


SUPPORTED_LANGUAGES = {
    "az": "Azərbaycan dili",
    "en": "English",
}


def normalise_language(value, fallback="en"):
    """Return a supported ISO-style UI language code."""

    language = str(value or "").strip().lower()
    return language if language in SUPPORTED_LANGUAGES else fallback


def language_for_widget(widget, fallback="en"):
    """Resolve the active language inherited by a dialog or child widget."""

    current = widget
    while current is not None:
        language = current.property("opa_language")
        if language in SUPPORTED_LANGUAGES:
            return language
        parent_widget = getattr(current, "parentWidget", None)
        current = parent_widget() if callable(parent_widget) else None
    application = QApplication.instance()
    if application is not None:
        for top_level in application.topLevelWidgets():
            language = top_level.property("opa_language")
            if language in SUPPORTED_LANGUAGES:
                return language
    return normalise_language(fallback)


def translate_for_widget(widget, text):
    """Translate text for native dialogs that are outside the widget tree."""

    return translate_text(text, language_for_widget(widget))


class LocalizedStatusBar(QStatusBar):
    """Status bar that translates every transient message at its source."""

    def __init__(self, language_provider, parent=None):
        super().__init__(parent)
        self._language_provider = language_provider
        self._source_message = ""
        self._last_timeout = 0

    def showMessage(self, message, timeout=0):
        self._source_message = message
        self._last_timeout = timeout
        language = normalise_language(self._language_provider())
        super().showMessage(translate_text(message, language), timeout)

    def clearMessage(self):
        self._source_message = ""
        self._last_timeout = 0
        super().clearMessage()

    def retranslate_current_message(self):
        """Refresh an already visible message after a live language switch."""

        if not self._source_message:
            return
        language = normalise_language(self._language_provider())
        super().showMessage(
            translate_text(self._source_message, language),
            self._last_timeout,
        )


# Exact translations are intentionally kept in one auditable catalogue.  Model
# names, units, acronyms and identifiers remain unchanged in both languages.
AZ_TRANSLATIONS = {
    # Application shell and Settings.
    "Orbital Perturbation Analyzer": "Orbital Perturbasiya Analizatoru",
    "ORBITAL PERTURBATION ANALYZER": "ORBİTAL PERTURBASİYA ANALİZATORU",
    "ORBITAL DYNAMICS": "ORBİTAL DİNAMİKA",
    "MULTI-BODY DYNAMICS CONSOLE  //  SYNTHETIC GEO DEMO  //  OPA": "ÇOXCİSİMLİ DİNAMİKA KONSOLU  //  SYNTHETIC GEO DEMO  //  OPA",
    "Real-time multi-body perturbation monitoring, visualization, and orbital propagation.": "Çoxcisimli perturbasiyanın real vaxt monitorinqi, vizuallaşdırılması və orbital propaqasiya.",
    "SETTINGS": "PARAMETRLƏR",
    "Close settings": "Parametrləri bağla",
    "PROGRAM &\nCONFIGURATION": "PROQRAM VƏ\nKONFİQURASİYA",
    "ADMIN ACCESS": "ADMİN GİRİŞİ",
    "CREDITS": "MÜƏLLİFLƏR",
    "Program & Configuration": "Proqram və konfiqurasiya",
    "Application identity, active flight-dynamics models and numerical precision.": "Tətbiq məlumatları, aktiv uçuş-dinamikası modelləri və ədədi dəqiqlik.",
    "INTERFACE APPEARANCE": "İNTERFEYS GÖRÜNÜŞÜ",
    "Theme": "Mövzu",
    "Normal": "Normal",
    "Retro": "Retro",
    "Use the established modern mission-control interface.": "Mövcud müasir missiya-idarəetmə interfeysindən istifadə et.",
    "Use the Windows XP-inspired engineering interface.": "Windows XP üslublu mühəndislik interfeysindən istifadə et.",
    "Language": "Dil",
    "Azerbaijani": "Azərbaycan dili",
    "Normal and Retro update the complete interface immediately. Save Configuration to restore the selected theme on the next launch. Calculations are unchanged.": "Normal və Retro bütün interfeysi dərhal yeniləyir. Növbəti açılışda seçilmiş mövzunu bərpa etmək üçün Konfiqurasiyanı yadda saxlayın. Hesablamalar dəyişmir.",
    "Azerbaijani and English update the active interface immediately.": "Azərbaycan dili və English seçimləri aktiv interfeysi dərhal yeniləyir.",
    "Public Mode is always the startup state. Admin content is loaded only from a signed, encrypted package authorized for this Windows user/device. Private files stay outside the application folder, so sharing a ZIP of the program does not include them. Passwords, private paths and unlock state are never saved.": "Proqram həmişə İctimai rejimdə açılır. Admin məzmunu yalnız bu Windows istifadəçisi və cihazı üçün icazəli, imzalanmış və şifrələnmiş paketdən yüklənir. Məxfi fayllar proqram qovluğundan kənarda qalır və proqramın ZIP arxivinə daxil olmur. Parol, məxfi yollar və açıq sessiya heç vaxt yadda saxlanmır.",
    "LOCAL ADMIN STORAGE": "LOKAL ADMİN SAXLANCI",
    "Device": "Cihaz",
    "Encrypted package": "Şifrələnmiş paket",
    "Only readiness is shown here. External private locations are never displayed, copied into the project, or written to normal settings.": "Burada yalnız hazırlıq vəziyyəti göstərilir. Xarici məxfi ünvanlar göstərilmir, layihəyə köçürülmür və adi parametrlərə yazılmır.",
    "PROVISIONED FOR THIS WINDOWS USER/DEVICE": "BU WINDOWS İSTİFADƏÇİSİ/CİHAZI ÜÇÜN HAZIRDIR",
    "SETUP REQUIRED": "QURAŞDIRMA TƏLƏB OLUNUR",
    "ENCRYPTED PACKAGE READY OUTSIDE APPLICATION FOLDER": "ŞİFRƏLƏNMİŞ PAKET PROQRAM QOVLUĞUNDAN KƏNARDA HAZIRDIR",
    "EXTERNAL PACKAGE NOT INSTALLED": "XARİCİ PAKET QURAŞDIRILMAYIB",
    "DEVICE SETUP": "CİHAZ QURAŞDIRMASI",
    "Verification key": "Yoxlama açarı",
    "Select the provisioned Ed25519 public key": "Təqdim edilmiş Ed25519 açıq açarını seçin",
    "BROWSE…": "SEÇ…",
    "ENROLL THIS DEVICE": "BU CİHAZI QEYDƏ AL",
    "Enrollment generates a unique random device key protected by Windows DPAPI. Re-enrollment invalidates packages made for the previous device identity.": "Qeydiyyat Windows DPAPI ilə qorunan unikal təsadüfi cihaz açarı yaradır. Yenidən qeydiyyat əvvəlki cihaz kimliyi üçün hazırlanmış paketləri etibarsız edir.",
    "SIGNED ADMIN PACKAGE": "İMZALANMIŞ ADMİN PAKETİ",
    "ADMIN PASSWORD": "ADMİN PAROLU",
    "Package": "Paket",
    "Select a local .opa-admin package": "Lokal .opa-admin paketini seçin",
    "Admin password": "Admin parolu",
    "Password is used in memory only": "Parol yalnız yaddaşda istifadə olunur",
    "UNLOCK": "KİLİDİ AÇ",
    "LOG OUT": "ÇIXIŞ ET",
    "PUBLIC MODE — LOCKED": "İCTİMAİ REJİM — KİLİDLİ",
    "Device enrollment completed.": "Cihaz qeydiyyatı tamamlandı.",
    "Admin package unlocked for this session.": "Admin paketi bu sessiya üçün açıldı.",
    "Admin session cleared; Public Mode is active.": "Admin sessiyası təmizləndi; İctimai rejim aktivdir.",
    "APPLICATION": "TƏTBİQ",
    "VERSION": "VERSİYA",
    "MISSION": "MİSSİYA",
    "REFERENCE FRAME": "REFERANS ÇƏRÇİVƏSİ",
    "Earth-centred J2000": "Yer-mərkəzli J2000",
    "EARTH GRAVITY": "YER CAZİBƏSİ",
    "EPHEMERIS": "EFEMERİD",
    "PERTURBATIONS": "PERTURBASİYALAR",
    "NUMERICAL PRECISION": "ƏDƏDİ DƏQİQLİK",
    "Relative tol.": "Nisbi dözümlülük",
    "Absolute tol.": "Mütləq dözümlülük",
    "Maximum step [s]": "Maksimum addım [s]",
    "IERS EOP correction": "IERS EOP düzəlişi",
    "Use bundled UT1−UTC and polar-motion Earth orientation data.": "Daxili UT1−UTC və qütb hərəkəti Yer orientasiyası məlumatlarından istifadə et.",
    "APPLY TO SESSION": "SEANSA TƏTBİQ ET",
    "SAVE CONFIGURATION": "KONFİQURASİYANI YADDA SAXLA",
    "✓ Configuration updated": "✓ Konfiqurasiya yeniləndi",
    "Configuration saved": "Konfiqurasiya yadda saxlanıldı",
    "Configuration saved.": "Konfiqurasiya yadda saxlanıldı.",
    "Credits": "Müəlliflər",
    "Design and development contributors to the Orbital Perturbation Analyzer.": "Orbital Perturbasiya Analizatorunun dizayn və inkişaf müəllifləri.",
    "REFRESH APPLICATION": "TƏTBİQİ YENİDƏN BAŞLAT",
    "Restart the application cleanly without closing it manually.": "Tətbiqi əl ilə bağlamadan təmiz şəkildə yenidən başladın.",
    "Open appearance, configuration and credits.": "Görünüş, konfiqurasiya və müəlliflər bölməsini aç.",

    # Main navigation.
    "LIVE UPDATE  ·  1 s": "CANLI YENİLƏNMƏ  ·  1 s",
    "EGM96 4×4  ·  DE440  ·  J2000  ·  MOON / SUN / SRP": "EGM96 4×4  ·  DE440  ·  J2000  ·  AY / GÜNƏŞ / SRP",
    "LIVE COORDINATES": "CANLI KOORDİNATLAR",
    "LIVE MONITOR": "CANLI MONİTOR",
    "PERTURBATION": "PERTURBASİYA",
    "PERTURBATION GRAPH": "PERTURBASİYA QRAFİKİ",
    "ORBITAL VIEW": "ORBİT GÖRÜNÜŞÜ",
    "2D SYSTEM VIEW": "2D SİSTEM GÖRÜNÜŞÜ",
    "REFERENCE LAB": "REFERANS LABORATORİYASI",
    "ECLIPSE": "TUTULMA",
    "ECLIPSE PREDICTION": "TUTULMA PROQNOZU",
    "SUN OUTAGE": "GÜNƏŞ MANEƏSİ",
    "Predict when the Sun crosses the receiving antenna beam behind the active GEO slot. Times use WGS-84 station geometry and the JPL DE440 apparent Sun direction.": "Günəşin aktiv GEO slotunun arxasında qəbuledici antenanın şüasından keçdiyi vaxtları proqnozlaşdırın. Vaxtlar WGS-84 stansiya həndəsəsi və JPL DE440 görünən Günəş istiqaməti ilə hesablanır.",
    "SUN OUTAGE INPUTS — ITU-R S.1525-1": "GÜNƏŞ MANEƏSİ GİRİŞLƏRİ — ITU-R S.1525-1",
    "Ground station:": "Yerüstü stansiya:",
    "Year:": "İl:",
    "Downlink frequency:": "Qəbul tezliyi:",
    "Antenna diameter:": "Antenanın diametri:",
    "Active GEO slot:": "Aktiv GEO slotu:",
    "Nominal slot from spacecraft reference": "Peykin referansından nominal orbital mövqe",
    "Synthetic nominal GEO slot": "Sintetik nominal GEO mövqeyi",
    "Fixed-slot estimate from state epoch": "Vəziyyət epoxasından hesablanmış sabit mövqe təxmini",
    "GEO longitude unavailable; check the spacecraft state or reference.": "GEO uzunluğu müəyyən edilmədi; peykin vəziyyətini və ya referansını yoxlayın.",
    "Frequency and antenna diameter must match the receiving link. The result is the Sun-disc + 3 dB beam intersection window; an actual carrier outage also depends on link margin and solar flux.": "Tezlik və antenanın diametri qəbuledici xəttə uyğun olmalıdır. Nəticə Günəş diski ilə 3 dB şüanın kəsişmə intervalıdır; real daşıyıcı kəsilməsi həmçinin rabitə ehtiyatından və Günəş axınından asılıdır.",
    "CALCULATE SUN OUTAGE": "GÜNƏŞ MANEƏSİNİ HESABLA",
    "CALCULATE FIRST": "ƏVVƏL HESABLA",
    "EXPORT SUN OUTAGE CSV": "GÜNƏŞ MANEƏSİ CSV-SİNİ İXRAC ET",
    "IMPORT REFERENCE SCHEDULE": "REFERANS CƏDVƏLİNİ İDXAL ET",
    "PREDICTED SUN OUTAGE WINDOWS": "PROQNOZLAŞDIRILMIŞ GÜNƏŞ MANEƏSİ İNTERVALLARI",
    "REFERENCE SCHEDULE COMPARISON": "REFERANS CƏDVƏLİ MÜQAYİSƏSİ",
    "ERROR METRICS — MATCHED EVENTS ONLY": "XƏTA METRİKLƏRİ — YALNIZ UYĞUN HADİSƏLƏR",
    "COMPARISON METRICS — MATCHED EVENTS ONLY": "MÜQAYİSƏ METRİKLƏRİ — YALNIZ UYĞUN HADİSƏLƏR",
    "CENTER MAE": "MƏRKƏZ MAE",
    "CENTER BIAS": "MƏRKƏZ SÜRÜŞMƏSİ",
    "DURATION MAPE": "MÜDDƏT MAPE",
    "START MAE": "BAŞLANĞIC MAE",
    "END MAE": "SON MAE",
    "DURATION MAE": "MÜDDƏT MAE",
    "MAX |START / END|": "MAKS |BAŞLANĞIC / SON|",
    "START BIAS": "BAŞLANĞIC SÜRÜŞMƏSİ",
    "END BIAS": "SON SÜRÜŞMƏSİ",
    "DURATION BIAS": "MÜDDƏT SÜRÜŞMƏSİ",
    "MATCHED EVENTS": "UYĞUN HADİSƏLƏR",
    "Mean absolute start-time error": "Başlanğıc vaxtının orta mütləq xətası",
    "Mean absolute end-time error": "Son vaxtının orta mütləq xətası",
    "Mean absolute window-length error": "İnterval müddətinin orta mütləq xətası",
    "Largest contact-boundary error": "Ən böyük kontakt sərhədi xətası",
    "Signed model − reference": "İşarəli model − referans",
    "Included in these metrics": "Bu metriklərə daxil edilib",
    "Reference midpoint vs geometric peak": "Referans intervalının ortası ilə həndəsi maksimumun müqayisəsi",
    "Signed peak − reference midpoint": "İşarəli maksimum − referans intervalının ortası",
    "Mean absolute schedule-duration difference": "Cədvəl müddətinin orta mütləq faiz fərqi",
    "Choose the receiving link parameters and calculate the yearly schedule.": "Qəbuledici xətt parametrlərini seçin və illik cədvəli hesablayın.",
    "Date UTC": "UTC tarixi",
    "Satellite": "Peyk",
    "Start UTC": "Başlanğıc UTC",
    "Peak UTC": "Maksimum UTC",
    "End UTC": "Son UTC",
    "Peak Baku (UTC+4)": "Maksimum Bakı (UTC+4)",
    "Duration": "Müddət",
    "Min. separation": "Min. ayrılma",
    "Risk threshold": "Risk həddi",
    "Reference start": "Referans başlanğıcı",
    "Reference midpoint": "Referans intervalının ortası",
    "Reference end": "Referans sonu",
    "Reference duration": "Referans müddəti",
    "Model start": "Model başlanğıcı",
    "Model peak": "Model maksimumu",
    "Model end": "Model sonu",
    "Model duration": "Model müddəti",
    "Start error": "Başlanğıc xətası",
    "End error": "Son xətası",
    "Duration error": "Müddət xətası",
    "Center difference": "Mərkəz fərqi",
    "Start difference": "Başlanğıc fərqi",
    "End difference": "Son fərqi",
    "Duration difference": "Müddət fərqi",
    "Duration difference %": "Müddət fərqi %",
    "MATCHED": "UYĞUN",
    "MISSING MODEL EVENT": "MODEL HADİSƏSİ YOXDUR",
    "EXTRA MODEL EVENT": "ƏLAVƏ MODEL HADİSƏSİ",
    "AWAITING MODEL RUN": "MODEL HESABI GÖZLƏNİLİR",
    "UNIDENTIFIED": "MÜƏYYƏN EDİLMƏYİB",
    "Method: ITU-R S.1525-1 Annex 2 beam geometry, WGS-84 Earth station, fixed nominal GSO slot and JPL DE440 apparent Sun. No eclipse or propagation result is modified.": "Metod: ITU-R S.1525-1 Əlavə 2 şüa həndəsəsi, WGS-84 yerüstü stansiya, sabit nominal GSO slotu və JPL DE440 görünən Günəş. Heç bir tutulma və ya propaqasiya nəticəsi dəyişdirilmir.",
    "PROPAGATION": "PROPAQASİYA",
    "GEO OPERATIONS": "GEO ƏMƏLİYYATLARI",
    "ORBIT DETERMINATION": "ORBİT TƏYİNİ",
    "ORBIT DETERMINATION WORKSPACE": "ORBİT TƏYİNİ İŞ SAHƏSİ",
    "MEASUREMENT-BASED ORBIT SOLUTION": "ÖLÇMƏ ƏSASLI ORBİT HƏLLİ",
    "Propagate the supplied reference state across a selected UTC arc, compare computed observations with real DEMO-A/DEMO-B tracking measurements, then estimate a corrected initial J2000 state with weighted batch least squares.": "Təqdim edilmiş referans vəziyyəti seçilmiş UTC intervalı boyunca propaqasiya edin, hesablanmış müşahidələri real Bakı/Naxçıvan izləmə ölçmələri ilə müqayisə edin, sonra çəkili paket ən kiçik kvadratlar üsulu ilə düzəldilmiş ilkin J2000 vəziyyətini qiymətləndirin.",
    "BUNDLED DATASET  ·  READY": "DAXİLİ DATASET  ·  HAZIR",
    "OD SOLUTION  ·  AVAILABLE": "ORBİT TƏYİNİ HƏLLİ  ·  HAZIRDIR",
    "OD SOLUTION  ·  ERROR": "ORBİT TƏYİNİ HƏLLİ  ·  XƏTA",
    "DATASET ERROR": "DATASET XƏTASI",
    "MEASUREMENTS": "ÖLÇMƏLƏR",
    "GROUND STATIONS": "YERÜSTÜ STANSİYALAR",
    "ESTIMATION": "QİYMƏTLƏNDİRMƏ",
    "RESIDUALS": "QALIQLAR",
    "DETERMINATIONS": "TƏYİN EDİLMİŞ ORBİTLƏR",
    "VALIDATION": "YOXLAMA",
    "MEASUREMENT DATASET": "ÖLÇMƏ DATASETİ",
    "Loading bundled OD dataset...": "Daxili orbit təyini dataseti yüklənir...",
    "RELOAD BUNDLED DATASET": "DAXİLİ DATASETİ YENİDƏN YÜKLƏ",
    "ESTIMATION ARC — UTC": "QİYMƏTLƏNDİRMƏ İNTERVALI — UTC",
    "Start epoch:": "Başlanğıc epoxası:",
    "End epoch:": "Son epoxa:",
    "Measurements in selected arc: —": "Seçilmiş intervaldakı ölçmələr: —",
    "WGS-84 station coordinates, fixed generic OD biases and 1σ measurement noise are applied directly in the observation model.": "WGS-84 stansiya koordinatları, sabit generic OD sürüşmələri və 1σ ölçmə səs-küyü birbaşa müşahidə modelində tətbiq edilir.",
    "OPA FORCE MODEL — J2000": "OPA QÜVVƏ MODELİ — J2000",
    "Earth EGM96": "Yer EGM96",
    "Moon gravity": "Ay cazibəsi",
    "Sun gravity": "Günəş cazibəsi",
    "SYNTHETIC GEO DEMO box-wing SRP": "SYNTHETIC GEO DEMO box-wing SRP",
    "CP scale:": "CP miqyası:",
    "WEIGHTED BATCH LEAST SQUARES": "ÇƏKİLİ PAKET ƏN KİÇİK KVADRATLAR",
    "SUPPLIED PROPAGATION FILE": "VERİLMİŞ PROPAQASİYA FAYLI",
    "File prefit RMS [km]": "Fayl ilkin RMS [km]",
    "Maximum iterations:": "Maksimum iterasiya:",
    "Post-fit rejection [σ]:": "Həll sonrası kənarlaşdırma [σ]:",
    "RUN ORBIT DETERMINATION": "ORBİT TƏYİNİNİ İŞƏ SAL",
    "REFRESH MEMORY": "YADDAŞI YENİLƏ",
    "Clear accumulated least-squares corrections and restart from the supplied orbit.": "Yığılmış ən kiçik kvadratlar düzəlişlərini sil və təqdim edilmiş orbitdən yenidən başla.",
    "No orbit-determination solution has been run.": "Hələ orbit təyini həlli işə salınmayıb.",
    "Run orbit determination to compare the propagated solution with the supplied reference orbit.": "Propaqasiya edilmiş həlli təqdim olunmuş referans orbitlə müqayisə etmək üçün orbit təyinini işə salın.",
    "USE CORRECTED STATE IN PROPAGATION": "DÜZƏLDİLMİŞ VƏZİYYƏTİ PROPAQASİYADA İSTİFADƏ ET",
    "Run": "Gediş",
    "Normal RMS [km]": "Normal RMS [km]",
    "LS RMS [km]": "ƏKK RMS [km]",
    "Min [km]": "Min [km]",
    "Max [km]": "Maks [km]",
    "Last [km]": "Son [km]",
    "Improvement": "Yaxşılaşma",
    "Weighted RMS": "Çəkili RMS",
    "Weighted prefit": "İlkin çəkili RMS",
    "Weighted postfit": "Son çəkili RMS",
    "Noon ΔR [m]": "Günorta ΔR [m]",
    "Noon ΔV [mm/s]": "Günorta ΔV [mm/s]",
    "Max ΔR [m]": "Maks ΔR [m]",
    "Last ΔR [m]": "Son ΔR [m]",
    "Component": "Komponent",
    "Correction": "Düzəliş",
    "Corrected": "Düzəldilmiş",
    "Observed": "Müşahidə",
    "Quality": "Keyfiyyət",
    "Station": "Stansiya",
    "Type": "Növ",
    "Noise": "Səs-küy",
    "Count": "Say",
    "Rejected": "Kənarlaşdırılıb",
    "Pre mean": "İlkin orta",
    "Pre RMS": "İlkin RMS",
    "Post mean": "Son orta",
    "Post RMS": "Son RMS",
    "Unit": "Vahid",
    "Prefit": "İlkin uyğunluq",
    "Postfit": "Son uyğunluq",
    "Pre residual": "İlkin qalıq",
    "Post residual": "Son qalıq",
    "Used": "İstifadə",
    "Latitude [deg]": "Enlik [dərəcə]",
    "Longitude [deg]": "Uzunluq [dərəcə]",
    "Height [km]": "Hündürlük [km]",
    "Range bias [km]": "Məsafə sürüşməsi [km]",
    "Az bias [deg]": "Azimut sürüşməsi [dərəcə]",
    "El bias [deg]": "Hündürlük bucağı sürüşməsi [dərəcə]",
    "Range σ [km]": "Məsafə σ [km]",
    "Az σ [deg]": "Azimut σ [dərəcə]",
    "El σ [deg]": "Hündürlük bucağı σ [dərəcə]",
    "Pressure [mbar]": "Təzyiq [mbar]",
    "Temp [°C]": "Temperatur [°C]",
    "FULL SCREEN  [F11]": "TAM EKRAN  [F11]",
    "EXIT FULL SCREEN  [F11]": "TAM EKRANDAN ÇIX  [F11]",
    "FULL SCREEN": "TAM EKRAN",
    "EXIT FULL SCREEN  [ESC]": "TAM EKRANDAN ÇIX  [ESC]",
    "EXIT  [ESC]": "ÇIXIŞ  [ESC]",
    "Show only this graph. Press Esc to return.": "Yalnız bu qrafiki göstər. Qayıtmaq üçün Esc basın.",
    "Return to the complete application.": "Tam tətbiq görünüşünə qayıt.",
    "Toggle application full screen. Press Esc to exit.": "Tətbiqi tam ekran rejiminə keçir. Çıxmaq üçün Esc basın.",
    "RESET VIEW": "GÖRÜNÜŞÜ SIFIRLA",
    "EXPAND ORBIT": "ORBİTİ GENİŞLƏNDİR",
    "Show only the orbit graph in full screen.": "Yalnız orbit qrafikini tam ekranda göstər.",
    "VISIBLE OBJECTS — TLE / GCRS J2000": "GÖRÜNƏN OBYEKTLƏR — TLE / GCRS J2000",
    "● EARTH (origin)": "● YER (başlanğıc)",
    "LIVE COORDINATES — ABSOLUTE GCRS J2000 [km]": "CANLI KOORDİNATLAR — MÜTLƏQ GCRS J2000 [km]",

    # Common labels and status.
    "View:": "Görünüş:",
    "Visual emphasis:": "Vizual vurğu:",
    "RESET ALL 1×": "HAMISINI 1× SIFIRLA",
    "Initial": "İlkin",
    "Final": "Final",
    "Change": "Dəyişmə",
    "Element": "Element",
    "Distance:": "Məsafə:",
    "Earth-Moon Distance:": "Yer–Ay məsafəsi:",
    "Earth-Sun Distance:": "Yer–Günəş məsafəsi:",
    "Magnitude:": "Modul:",
    "Active force modules:": "Aktiv qüvvə modulları:",
    "Displayed sum:": "Göstərilən cəm:",
    "Waiting for live state...": "Canlı vəziyyət gözlənilir...",
    "SYSTEM STATUS": "SİSTEM STATUSU",
    "UTC: Waiting...": "UTC: Gözlənilir...",
    "Time range:": "Vaxt intervalı:",
    "Parameter:": "Parametr:",
    "Force sources:": "Qüvvə mənbələri:",
    "Combined": "Birləşmiş",
    "PREDICT PAST + FUTURE": "KEÇMİŞİ + GƏLƏCƏYİ PROQNOZLA",
    "CANCEL PREDICTION": "PROQNOZU LƏĞV ET",
    "CANCELLING...": "LƏĞV EDİLİR...",
    "Perturbation prediction cancelled.": "Perturbasiya proqnozu ləğv edildi.",
    "< PAST": "< KEÇMİŞ",
    "CENTER NOW": "İNDİYƏ MƏRKƏZLƏ",
    "FUTURE >": "GƏLƏCƏK >",
    "Projection:": "Proyeksiya:",
    "Scale:": "Miqyas:",
    "Focus:": "Fokus:",
    "Selected:": "Seçilmiş:",
    "Status": "Vəziyyət",
    "READY": "HAZIR",
    "INSUFFICIENT DATA": "MƏLUMAT KİFAYƏT DEYİL",
    "CANCEL": "LƏĞV ET",
    "CLEAR OUTPUT": "NƏTİCƏNİ TƏMİZLƏ",
    "CALCULATING...": "HESABLANIR...",

    # Telemetry, model and validation pages.
    "CELESTIAL EPHEMERIDES — DE440 / J2000": "GÖY CİSİMLƏRİ EFEMERİDLƏRİ — DE440 / J2000",
    "PERTURBATION ACCELERATION — THIRD-BODY + SRP": "PERTURBASİYA TƏCİLİ — ÜÇÜNCÜ CİSİM + SRP",
    "Moon — DE440": "Ay — DE440",
    "Sun — DE440": "Günəş — DE440",
    "Moon": "Ay",
    "Sun β": "Günəş β",
    "EARTH": "YER",
    "MOON": "AY",
    "Moon |a|:": "Ay |a|:",
    "Moon · Sun · SRP": "Ay · Günəş · SRP",
    "Sun β |a|:": "Günəş β |a|:",
    "Sunlight / CP:": "Günəş işığı / CP:",
    "DATA SOURCE AND REFERENCE FRAMES": "MƏLUMAT MƏNBƏYİ VƏ REFERANS ÇƏRÇİVƏLƏRİ",
    "REFRESH STATUS": "STATUSU YENİLƏ",
    "UPDATE TLE": "TLE-Nİ YENİLƏ",
    "UPDATE TLE FROM CELESTRAK": "TLE-Nİ CELESTRAK-DAN YENİLƏ",
    "TLE: UPDATING...": "TLE: YENİLƏNİR...",
    "TLE: UPDATE FAILED": "TLE: YENİLƏMƏ UĞURSUZ OLDU",
    "REPRODUCIBLE TIME MODE": "TƏKRARLANAN VAXT REJİMİ",
    "Mode:": "Rejim:",
    "Epoch:": "Epoxa:",
    "APPLY TIME MODE": "VAXT REJİMİNİ TƏTBİQ ET",
    "LIVE": "CANLI",
    "FIXED": "SABİT",
    "EARTH ORIENTATION PARAMETERS — IERS": "YER ORİENTASİYA PARAMETRLƏRİ — IERS",
    "NUMERICAL SETTINGS": "ƏDƏDİ PARAMETRLƏR",
    "Relative tolerance:": "Nisbi dözümlülük:",
    "Absolute tolerance:": "Mütləq dözümlülük:",
    "Validation horizon [min]:": "Yoxlama intervalı [dəq]:",
    "VALIDATION, ERROR BUDGET, AND LOGGING": "YOXLAMA, XƏTA BÜDCƏSİ VƏ JURNALLAMA",
    "RUN VALIDATION + ERROR BUDGET": "YOXLAMA + XƏTA BÜDCƏSİNİ İŞƏ SAL",
    "START LIVE CSV/JSON LOG": "CANLI CSV/JSON JURNALINI BAŞLAT",
    "STOP LOGGING": "JURNALLAMANI DAYANDIR",
    "Logging is stopped.": "Jurnallama dayandırılıb.",
    "MODEL PROVENANCE — CONSTANTS, SOURCES, LIMITATIONS": "MODEL MƏNŞƏYİ — SABİTLƏR, MƏNBƏLƏR, MƏHDUDİYYƏTLƏR",
    "Group": "Qrup",
    "Quantity": "Kəmiyyət",
    "Source": "Mənbə",
    "Value": "Qiymət",
    "FORCE MODEL CONFIGURATION": "QÜVVƏ MODELİ KONFİQURASİYASI",
    "REFERENCE DATASET": "REFERANS MƏLUMAT DƏSTİ",
    "OPEN REFERENCE FOLDER": "REFERANS QOVLUĞUNU AÇ",
    "REFRESH REFERENCES": "REFERANSLARI YENİLƏ",
    "Open the folder containing bundled references, the user format guide and drop-in manifests.": "Daxili referansların, istifadəçi formatı təlimatının və əlavə edilən manifestlərin olduğu qovluğu aç.",
    "Rescan *.opa-reference.json manifests and validate their CSV files.": "*.opa-reference.json manifestlərini yenidən axtar və CSV fayllarını yoxla.",
    "Validating local data...": "Lokal məlumat yoxlanılır...",
    "Select:": "Seçim:",
    "Source:": "Mənbə:",
    "Satellite:": "Peyk:",
    "Sampling:": "Nümunələmə:",
    "Source frame:": "Mənbə çərçivəsi:",
    "Force model:": "Qüvvə modeli:",
    "Available:": "Mövcuddur:",
    "Status:": "Vəziyyət:",
    "VALIDATION CONTROLS": "YOXLAMA İDARƏETMƏLƏRİ",
    "Use empirical reference calibration": "Empirik referans kalibrasiyasından istifadə et",
    "RUN SELECTED MODEL": "SEÇİLMİŞ MODELİ İŞƏ SAL",
    "EXPORT MODEL CSV": "MODEL CSV-SİNİ İXRAC ET",
    "VALIDATED MODEL / REFERENCE COMPARISON": "YOXLANMIŞ MODEL / REFERANS MÜQAYİSƏSİ",
    "Chart view:": "Qrafik görünüşü:",
    "POSITION ERROR": "MÖVQE XƏTASI",
    "SCIENTIFIC SUMMARY": "ELMİ XÜLASƏ",
    "Validation metrics will appear here.": "Yoxlama metrikləri burada görünəcək.",

    # Eclipse page.
    "ECLIPSE INITIAL STATE — J2000": "TUTULMANIN İLKİN VƏZİYYƏTİ — J2000",
    "Epoch UTC:": "UTC epoxası:",
    "USE CURRENT SYNTHETIC GEO DEMO TLE": "CARİ SYNTHETIC GEO DEMO TLE-DƏN İSTİFADƏ ET",
    "COPY PROPAGATION INPUT": "PROPAQASİYA GİRİŞİNİ KOPYALA",
    "ECLIPSE SEARCH SETTINGS": "TUTULMA AXTARIŞ PARAMETRLƏRİ",
    "SECONDS": "SANİYƏ",
    "MINUTES": "DƏQİQƏ",
    "HOURS": "SAAT",
    "DAYS": "GÜN",
    "Moon gravity": "Ay cazibəsi",
    "Sun gravity": "Günəş cazibəsi",
    "Physical SRP trajectory effect": "Fiziki SRP trayektoriya təsiri",
    "Search duration:": "Axtarış müddəti:",
    "Output/search step:": "Nəticə/axtarış addımı:",
    "Oblate Earth shadow": "Basılmış ellipsoid Yer kölgəsi",
    "Light-time Moon position": "İşıq-vaxt düzəlişli Ay mövqeyi",
    "Models the Earth shadow as a WGS-84 ellipsoid instead of a sphere. The result is unchanged near mid-season but can differ at the edges. It is off by default because the bundled references use a spherical shadow.": "Yer kölgəsini kürə əvəzinə WGS-84 ellipsoidi kimi modelləşdirir. Mövsümün ortasında nəticə dəyişmir, kənarlarda isə fərqlənə bilər. Daxili referanslar sferik kölgədən istifadə etdiyi üçün standart olaraq söndürülüb.",
    "Uses the light-time-corrected Moon position (19 arcseconds). This is physically correct for occultation geometry, but it is off by default because both references use the geometric position.": "Ay mövqeyinə işıq-vaxt düzəlişi tətbiq edir (19 bucaq saniyəsi). Örtülmə həndəsəsi üçün fiziki cəhətdən doğrudur, lakin hər iki referans geometrik mövqedən istifadə etdiyi üçün standart olaraq söndürülüb.",
    "Geometry:": "Həndəsə:",
    "FAST YEAR SEARCH — 1 HOUR → 1 MINUTE": "SÜRƏTLİ İLLİK AXTARIŞ — 1 SAAT → 1 DƏQİQƏ",
    "EXPORT YEAR CSV": "İLLİK CSV-Nİ İXRAC ET",
    "Year schedule:": "İllik cədvəl:",
    "CALCULATE ECLIPSE EVENTS": "TUTULMA HADİSƏLƏRİNİ HESABLA",
    "EXPORT ECLIPSE CSV": "TUTULMA CSV-SİNİ İXRAC ET",
    "Remaining: --:--:--": "Qalan vaxt: --:--:--",
    "ECLIPSE TIMELINE — SUNLIGHT / PENUMBRA / UMBRA": "TUTULMA ZAMAN XƏTTİ — GÜNƏŞ İŞIĞI / YARIMKÖLGƏ / TAM KÖLGƏ",
    "Detailed eclipse event:": "Ətraflı tutulma hadisəsi:",
    "Calculate events first": "Əvvəlcə hadisələri hesablayın",
    "ECLIPSE EVENT TABLE — UTC": "TUTULMA HADİSƏLƏRİ CƏDVƏLİ — UTC",
    "No standalone eclipse calculation has been run.": "Müstəqil tutulma hesablaması aparılmayıb.",
    "Penumbra entry UTC": "Yarımkölgəyə giriş UTC",
    "Umbra entry UTC": "Tam kölgəyə giriş UTC",
    "Umbra exit UTC": "Tam kölgədən çıxış UTC",
    "Penumbra exit UTC": "Yarımkölgədən çıxış UTC",
    "Umbra duration": "Tam kölgə müddəti",
    "Total eclipse": "Ümumi tutulma",
    "YEARLY ECLIPSE SCHEDULE — UTC": "İLLİK TUTULMA CƏDVƏLİ — UTC",
    "Choose a year and run the 1-minute year search.": "İli seçin və 1 dəqiqəlik illik axtarışı başladın.",
    "Date UTC": "Tarix UTC",
    "Event": "Hadisə",
    "REFERENCE COMPARISON — OUR OUTPUT vs BUNDLED DATA": "REFERANS MÜQAYİSƏSİ — BİZİM NƏTİCƏ vs DAXİLİ MƏLUMAT",
    "Reference:": "Referans:",
    "Tolerance:": "Dözümlülük:",
    "COMPARE CURRENT OUTPUT": "CARİ NƏTİCƏNİ MÜQAYİSƏ ET",
    "EXPORT COMPARISON CSV": "MÜQAYİSƏ CSV-SİNİ İXRAC ET",
    "RUN MODEL FOR SELECTED REFERENCE DATES + COMPARE": "SEÇİLMİŞ REFERANS TARİXLƏRİ ÜÇÜN MODELİ İŞƏ SAL + MÜQAYİSƏ ET",
    "Selected interval: —": "Seçilmiş interval: —",
    "Run the calculation. The result will explain in plain language how early or late the model is relative to the reference and show the likely cause.": "Hesablamanı başladın. Nəticə modelin referansa nəzərən nə qədər tez və ya gec olduğunu sadə dillə izah edəcək və ehtimal olunan səbəbi göstərəcək.",
    "Run the comparison to see how early or late the model is.": "Modelin nə qədər tez və ya gec olduğunu görmək üçün müqayisəni başladın.",
    "Check a bundled reference, or predict from your own J2000 state.": "Daxili referansı yoxlayın və ya öz J2000 vəziyyətinizdən proqnoz verin.",
    "Run an Eclipse calculation, then compare it with the selected reference.": "Tutulma hesablamasını başladın, sonra seçilmiş referansla müqayisə edin.",
    "Result": "Nəticə",
    "Shadow": "Kölgə",
    "Ref. entry (UTC)": "Ref. giriş (UTC)",
    "Model entry (UTC)": "Model giriş (UTC)",
    "Entry difference": "Giriş fərqi",
    "Ref. exit (UTC)": "Ref. çıxış (UTC)",
    "Model exit (UTC)": "Model çıxış (UTC)",
    "Exit difference": "Çıxış fərqi",
    "Duration difference": "Müddət fərqi",
    "Quality": "Keyfiyyət",
    "MATCH": "UYĞUNDUR",
    "DIFFERENCE": "FƏRQLİ",
    "MISSING OUTPUT": "MODEL NƏTİCƏSİ YOXDUR",
    "EXTRA OUTPUT": "MODELƏ ARTIQ",
    "SHARP": "DƏQİQ",
    "SOFT": "ORTA",
    "GRAZING": "SÜRÜŞKƏN",
    "MATCHES": "UYĞUNDUR",
    "DOES NOT MATCH": "UYĞUN DEYİL",
    "Contact sensitivity was not measured.": "Kontakt həssaslığı ölçülməyib.",

    # Propagation and Kepler pages.
    "INITIAL STATE — J2000": "İLKİN VƏZİYYƏT — J2000",
    "PROPAGATION SETTINGS": "PROPAQASİYA PARAMETRLƏRİ",
    "Include Moon perturbation": "Ay perturbasiyasını daxil et",
    "Include Sun third-body gravity": "Günəşin üçüncü-cisim cazibəsini daxil et",
    "Include solar radiation pressure — SYNTHETIC GEO DEMO": "Günəş radiasiya təzyiqini daxil et — SYNTHETIC GEO DEMO",
    "SELECT DATE / TIME": "TARİX / VAXT SEÇ",
    "Select Epoch UTC": "UTC EPOXASINI SEÇ",
    "Date (UTC)": "Tarix (UTC)",
    "Time (UTC)": "Vaxt (UTC)",
    "Open a UTC calendar and time selector; keyboard entry remains optional.": "UTC təqvimini və vaxt seçicisini açır; klaviatura ilə yazmaq məcburi deyil.",
    "Include solar radiation pressure — SYNTHETIC GEO DEMO": "Günəş radiasiya təzyiqini daxil et — SYNTHETIC GEO DEMO",
    "Active profile SRP model": "Aktiv profilin SRP modeli",
    "SYNTHETIC/DEMO fixed-coefficient SRP model": "SYNTHETIC/DEMO sabit əmsallı SRP modeli",
    "Manual SRP parameters": "Əl ilə SRP parametrləri",
    "Include solar radiation pressure — Manual": "Günəş radiasiya təzyiqini daxil et — Əl ilə",
    "SRP spacecraft model:": "SRP kosmik aparat modeli:",
    "SRP parameters:": "SRP parametrləri:",
    "MANUAL SRP INPUTS — EFFECTIVE AREA": "ƏL İLƏ SRP GİRİŞLƏRİ — EFFEKTİV SAHƏ",
    "Enter panel and body CP separately": "Panel və gövdə CP-sini ayrı daxil et",
    "Spacecraft mass:": "Kosmik aparatın kütləsi:",
    "Total area:": "Ümumi sahə:",
    "CP:": "CP:",
    "Panel area:": "Panel sahəsi:",
    "Panel CP:": "Panel CP-si:",
    "Body area (total − panel):": "Gövdə sahəsi (ümumi − panel):",
    "Body CP:": "Gövdə CP-si:",
    "Manual effective-area SRP · combined CP or separate panel/body CP with automatically derived body area · Earth umbra/penumbra": "Əl ilə effektiv-sahə SRP-si · ümumi CP və ya gövdə sahəsi avtomatik hesablanan ayrı panel/gövdə CP-si · Yer tam/yarımkölgəsi",
    "Choose the spacecraft parameters used only when solar pressure is enabled.": "Yalnız günəş təzyiqi aktiv olduqda istifadə ediləcək kosmik aparat parametrlərini seçin.",
    "USE CURRENT UTC": "CARİ UTC-DƏN İSTİFADƏ ET",
    "LOAD ACTIVE PROFILE": "AKTİV PROFİLİ YÜKLƏ",
    "PROPAGATE": "PROPAQASİYA ET",
    "SAVE TXT": "TXT YADDA SAXLA",
    "SAVE CSV": "CSV YADDA SAXLA",
    "PROPAGATION ANALYSIS": "PROPAQASİYA ANALİZİ",
    "PROPAGATED STATE — X / Y / Z / Vx / Vy / Vz": "PROPAQASİYA OLUNMUŞ VƏZİYYƏT — X / Y / Z / Vx / Vy / Vz",
    "EARTH-FIXED LONGITUDE — ITRS / STATION BOX": "YERƏ BAĞLI UZUNLUQ — ITRS / STANSİYA QUTUSU",
    "PERTURBATION FORCE PROFILE — MOON / SUN / SRP / TOTAL": "PERTURBASİYA QÜVVƏ PROFİLİ — AY / GÜNƏŞ / SRP / CƏM",
    "OSCULATING KEPLER ELEMENTS — HISTORY / GEOMETRY / TABLE": "OSKULYASİYA KEPLER ELEMENTLƏRİ — TARİXÇƏ / HƏNDƏSƏ / CƏDVƏL",
    "Propagation result will appear here.": "Propaqasiya nəticəsi burada görünəcək.",
    "30-DAY ELEMENT HISTORY": "30 GÜNLÜK ELEMENT TARİXÇƏSİ",
    "ORBIT GEOMETRY": "ORBİT HƏNDƏSƏSİ",
    "GM basis:": "GM əsası:",
    "Run a calculation to compare the initial and final epochs.": "İlkin və final epoxaları müqayisə etmək üçün hesablama aparın.",

    # Product/project and GEO extensions.
    "ACTIVE SPACECRAFT": "AKTİV KOSMİK APARAT",
    "PROFILES": "PROFİLLƏR",
    "File": "Fayl",
    "New": "Yeni",
    "Open": "Aç",
    "Save As": "Fərqli yadda saxla",
    "Refresh Application": "Tətbiqi yenidən başlat",
    "Exit": "Çıxış",
    "Spacecraft:": "Kosmik aparat:",
    "Spacecraft name": "Kosmik aparatın adı",
    "NEW": "YENİ",
    "DUPLICATE": "SURƏTİNİ ÇIXAR",
    "EDIT": "REDAKTƏ ET",
    "DELETE": "SİL",
    "IMPORT": "İDXAL ET",
    "EXPORT": "İXRAC ET",
    "OPEN": "AÇ",
    "SAVE": "YADDA SAXLA",
    "SAVE AS": "FƏRQLİ YADDA SAXLA",
    "OPEN PROJECT…": "LAYİHƏNİ AÇ…",
    "RECENT PROJECTS": "SON LAYİHƏLƏR",
    "NO RECENT PROJECTS": "SON LAYİHƏ YOXDUR",
    "CLEAR RECENT PROJECTS": "SON LAYİHƏLƏRİ TƏMİZLƏ",
    "NO PROJECT · UNSAVED WORKSPACE": "LAYİHƏ YOXDUR · İŞ SAHƏSİ YADDA SAXLANILMAYIB",
    "SATELLITE PROFILE": "PEYK PROFİLİ",
    "SATELLITE PROFILE MANAGER": "PEYK PROFİL MENECERİ",
    "IDENTITY / ORBIT SOURCE": "İDENTİKLİK / ORBİT MƏNBƏYİ",
    "BASIC": "ƏSAS",
    "ADVANCED": "TƏKMİL",
    "BASIC SPACECRAFT MODEL": "ƏSAS KOSMİK APARAT MODELİ",
    "DETAILED SPACECRAFT / PROPULSION MODEL": "ƏTRAFLI KOSMİK APARAT / HƏRƏKƏTVERİCİ MODELİ",
    "Cross-sectional / effective area [m²]": "En kəsik / effektiv sahə [m²]",
    "SRP coefficient / CP": "SRP əmsalı / CP",
    "These fields, together with the orbit source below, are enough to create and use a spacecraft. Propulsion and detailed surface properties are optional and remain under Advanced.": "Bu sahələr aşağıdakı orbit mənbəyi ilə birlikdə kosmik aparatı yaratmaq və istifadə etmək üçün kifayətdir. Hərəkətverici və ətraflı səth xüsusiyyətləri ixtiyaridir və Təkmil bölməsində qalır.",
    "SPACECRAFT PHYSICAL MODEL": "KOSMİK APARATIN FİZİKİ MODELİ",
    "FORCE MODEL / GEO DEFAULTS": "QÜVVƏ MODELİ / GEO STANDARTLARI",
    "SRP SPACECRAFT CASE — SHARED WITH PROPAGATION": "SRP KOSMİK APARAT HALI — PROPAQASİYA İLƏ ORTAQ",
    "Input source:": "Giriş mənbəyi:",
    "Existing / predefined spacecraft": "Mövcud / əvvəlcədən təyin edilmiş kosmik aparat",
    "Manual input": "Əl ilə giriş",
    "Manual area mode:": "Əl ilə sahə rejimi:",
    "CALCULATE SRP AT REFERENCE EPOCH": "REFERANS EPOXASINDA SRP HESABLA",
    "SYNTHETIC GEO DEMO or manual SRP acceleration will appear here.": "SYNTHETIC GEO DEMO və ya əl ilə SRP təcili burada görünəcək.",
    "TRAJECTORY PROPAGATION FOR ECLIPSE SEARCH": "TUTULMA AXTARIŞI ÜÇÜN TRAYEKTORİYA PROPAQASİYASI",
    "ECLIPSE DETECTION GEOMETRY": "TUTULMA AŞKARLAMA HƏNDƏSƏSİ",
    "USE ACTIVE SPACECRAFT STATE": "AKTİV KOSMİK APARAT VƏZİYYƏTİNDƏN İSTİFADƏ ET",
    "These switches only define the trajectory supplied to the detector. Eclipse detection itself always uses Sun–Earth/Moon–spacecraft geometry and does not require any perturbation switch.": "Bu açarlar yalnız detektora verilən trayektoriyanı müəyyən edir. Tutulmanın aşkarlanması həmişə Günəş–Yer/Ay–kosmik aparat həndəsəsindən istifadə edir və heç bir perturbasiya açarı tələb etmir.",
    "Earth central gravity — required": "Yerin mərkəzi cazibəsi — tələb olunur",
    "Earth EGM96 harmonics": "Yer EGM96 harmonikləri",
    "Moon third-body": "Ay üçüncü cisim",
    "Sun third-body": "Günəş üçüncü cisim",
    "Solar radiation pressure": "Günəş radiasiya təzyiqi",
    "IERS EOP default": "IERS EOP standartı",
    "IMPORT EPHEMERIS STATE JSON": "EFEMERİD VƏZİYYƏT JSON-UNU İDXAL ET",
    "USE PROFILE": "PROFİLDƏN İSTİFADƏ ET",
    "CLOSE": "BAĞLA",
    "Save": "Yadda saxla",
    "Cancel": "Ləğv et",
    "Discard": "Yadda saxlama",
    "Yes": "Bəli",
    "No": "Xeyr",
    "OK": "Oldu",
    "GEO STATION-KEEPING ANALYSIS": "GEO STANSİYADA SAXLAMA ANALİZİ",
    "ACTIVE PROJECT CONSTRAINTS": "AKTİV LAYİHƏ MƏHDUDİYYƏTLƏRİ",
    "ANALYZE LATEST PROPAGATION": "SON PROPAQASİYANI ANALİZ ET",
    "GEO OPERATIONS TREND": "GEO ƏMƏLİYYATLARI TRENDİ",

    # Detailed guidance, plot controls and engineering descriptions.
    "Language:": "Dil:",
    "History plots a, e, i, Ω, ω and ν at every propagation output epoch. Geometry keeps the initial/final 3D construction.": "Tarixçə hər propaqasiya nəticə epoxasında a, e, i, Ω, ω və ν qiymətlərini göstərir. Həndəsə ilkin/final 3D quruluşunu saxlayır.",
    "WEB CHECK — 398600.0": "VEB YOXLAMASI — 398600.0",
    "EGM96 PHYSICAL — 398600.4418": "EGM96 FİZİKİ — 398600.4418",
    "WEB CHECK reproduces the rounded Earth GM used by the cited online calculator. EGM96 PHYSICAL uses the propagation model's GM. This selection changes only the displayed Kepler elements.": "VEB YOXLAMASI göstərilən onlayn kalkulyatorun yuvarlaqlaşdırılmış Yer GM qiymətini təkrarlayır. EGM96 FİZİKİ propaqasiya modelinin GM qiymətindən istifadə edir. Bu seçim yalnız göstərilən Kepler elementlərini dəyişir.",
    "Visual-only scale: a amplifies initial/final size separation; e and i amplify both geometries; Ω, ω and ν amplify final change from the initial orbit. Visual scaling never changes the table. GM basis changes only displayed elements; propagation remains EGM96.": "Yalnız vizual miqyas: a ilkin/final ölçü fərqini, e və i hər iki həndəsəni, Ω, ω və ν isə ilkin orbitdən final dəyişməni böyüdür. Vizual miqyas cədvəli dəyişmir. GM əsası yalnız göstərilən elementləri dəyişir; propaqasiya EGM96 olaraq qalır.",
    "Earth-centred J2000 osculating elements · EGM96 GM = 398600.4418 km³/s² · angular changes use the shortest signed arc": "Yer-mərkəzli J2000 oskulyasiya elementləri · EGM96 GM = 398600.4418 km³/s² · bucaq dəyişmələri ən qısa işarəli qövsdən istifadə edir",
    "Sun X:": "Günəş X:",
    "Sun Y:": "Günəş Y:",
    "Sun Z:": "Günəş Z:",
    "SRP — BOX-WING": "SRP — QUTU-QANAD",
    "SRP — EFFECTIVE AREA": "SRP — EFFEKTİV SAHƏ",
    "Physical box-wing SRP uses the transparent public coefficient CP=1.0. No spacecraft calibration is bundled.": "Fiziki qutu-qanad SRP modeli şəffaf ictimai CP=1.0 əmsalından istifadə edir. Kosmik aparata aid kalibrasiya daxil edilməyib.",
    "MOON + SUN + SRP": "AY + GÜNƏŞ + SRP",
    "SPICE: ✓ Loaded": "SPICE: ✓ Yükləndi",
    "TLE: ✓ Loaded": "TLE: ✓ Yükləndi",
    "ax/ay/az are J2000 inertial components; aR/aT/aN are radial, along-track, and orbit-normal RTN components.": "ax/ay/az J2000 ətalət komponentləridir; aR/aT/aN radial, orbit boyunca və orbitə normal RTN komponentləridir.",
    "Moon, Sun β and physical SRP are independent; Combined is the vector sum. Public-mode SRP uses the explicit neutral CP=1.0 coefficient.": "Ay, Günəş β və fiziki SRP müstəqildir; Birləşmiş onların vektor cəmidir. İctimai rejimdə SRP açıq neytral CP=1.0 əmsalından istifadə edir.",
    "Zoom in deeply toward the focused object.": "Fokuslanmış obyektə doğru dərindən yaxınlaşdır.",
    "Zoom out from the focused object.": "Fokuslanmış obyektdən uzaqlaşdır.",
    "Click graph: enable wheel zoom  •  Click outside: page scroll  •  Double-click: deep focus zoom  •  3D: drag orbit camera  •  Crosshair: focused-frame horizontal / vertical coordinates": "Qrafikə klik: çarxla miqyası aktiv et  •  Kənara klik: səhifəni sürüşdür  •  İki klik: dərin fokus  •  3D: orbit kamerasını çək  •  Kursor: fokus çərçivəsinin üfüqi / şaquli koordinatları",
    "VIEW METRICS / Selected: --  •  Span: --": "GÖRÜNÜŞ METRİKLƏRİ / Seçilmiş: --  •  Aralıq: --",
    "EARTH / X: 0.000 / Y: 0.000 / Z: 0.000": "YER / X: 0.000 / Y: 0.000 / Z: 0.000",
    "FOCUS: EARTH / X: 0.000  •  Y: 0.000  •  Z: 0.000": "FOKUS: YER / X: 0.000  •  Y: 0.000  •  Z: 0.000",
    "Loading local TLE metadata...": "Lokal TLE metaməlumatları yüklənir...",
    "Satellite: Skyfield/SGP4 GCRS (Earth-centred inertial, J2000-aligned) / Moon: SPICE DE440, Earth-centred J2000, geometric (NONE) / Numerical propagator: Earth-centred J2000, km / s": "Peyk: Skyfield/SGP4 GCRS (Yer-mərkəzli ətalət, J2000 ilə uyğun) / Ay: SPICE DE440, Yer-mərkəzli J2000, geometrik (NONE) / Ədədi propaqator: Yer-mərkəzli J2000, km / s",
    "Use bundled IERS EOP (UT1−UTC + polar motion xp/yp)": "Daxili IERS EOP-dan istifadə et (UT1−UTC + qütb hərəkəti xp/yp)",
    "Applies the bundled finals2000A series to J2000↔ITRS, EGM96 Earth harmonics, GEO longitude and WGS-84 products.": "Daxili finals2000A sırasını J2000↔ITRS çevrilməsinə, EGM96 Yer harmoniklərinə, GEO uzunluğuna və WGS-84 nəticələrinə tətbiq edir.",
    "Maximum step [s]:": "Maksimum addım [s]:",
    "Every number the model uses, where it comes from, and what is deliberately left out. Values are read from the running code, not copied, so this panel cannot fall behind the model.": "Modelin istifadə etdiyi hər bir rəqəm, onun mənbəyi və qəsdən modelə daxil edilməyən hissələr. Qiymətlər kopyalanmır, işləyən koddan oxunur; buna görə bu panel modeldən geri qalmır.",
    "Downloading and validating TLE catalogue...": "TLE kataloqu endirilir və yoxlanılır...",
    "TLE: ERROR": "TLE: XƏTA",
    "Range changed. Run prediction to estimate past and future.": "İnterval dəyişdi. Keçmişi və gələcəyi qiymətləndirmək üçün proqnozu başladın.",
    "Force selection changed. Run prediction for the selected sources.": "Qüvvə seçimi dəyişdi. Seçilmiş mənbələr üçün proqnozu başladın.",
    "Propagating orbit backward and forward...": "Orbit geriyə və irəli propaqasiya olunur...",
    "Select the force model once, then run it with one action. Moon chooses the matching Moon-on/off reference scenario; Sun is fully selectable and its additional residual is reported transparently against the current reference dataset.": "Qüvvə modelini bir dəfə seçin, sonra bir əmrlə başladın. Ay uyğun Ay-aktiv/deaktiv referans ssenarisini seçir; Günəş sərbəst seçilir və onun əlavə residualı cari referans dəstinə qarşı açıq göstərilir.",
    "Choose a reference first by month, then by physical force model.": "Əvvəlcə aya, sonra fiziki qüvvə modelinə görə referans seçin.",
    "EGM96 4×4 + selectable DE440 Moon/Sun + physical box-wing SRP": "EGM96 4×4 + seçilə bilən DE440 Ay/Günəş + fiziki qutu-qanad SRP",
    "Empirical calibration is disabled; validation is physical-only.": "Empirik kalibrasiya söndürülüb; yoxlama yalnız fizikidir.",
    "PHYSICAL ONLY — calibration, scale, fit and bias are disabled": "YALNIZ FİZİKİ — kalibrasiya, miqyas, uyğunlaşdırma və sürüşmə söndürülüb",
    "MODEL + REFERENCE LONGITUDE": "MODEL + REFERANS UZUNLUĞU",
    "STATE RESIDUALS — ΔX / ΔY / ΔZ / ΔVx / ΔVy / ΔVz": "VƏZİYYƏT RESİDUALLARI — ΔX / ΔY / ΔZ / ΔVx / ΔVy / ΔVz",
    "X POSITION — MODEL + REFERENCE": "X MÖVQEYİ — MODEL + REFERANS",
    "Y POSITION — MODEL + REFERENCE": "Y MÖVQEYİ — MODEL + REFERANS",
    "Z POSITION — MODEL + REFERENCE": "Z MÖVQEYİ — MODEL + REFERANS",
    "SCENARIO / COMMON-STATE MOON EFFECT": "SSENARİ / EYNİ VƏZİYYƏTDƏ AY TƏSİRİ",
    "State residuals are calculated row-by-row as model minus supplied reference. X/Y share one scale and Vx/Vy share one scale. Z and Vz keep their own detail scales so their small physical variations remain visible. Longitude, component overlays, absolute position error and common-state Moon sensitivity remain available as separate views.": "Vəziyyət residualları hər sətirdə model minus verilmiş referans kimi hesablanır. X/Y bir miqyası, Vx/Vy isə başqa bir miqyası paylaşır. Kiçik fiziki dəyişmələrin görünməsi üçün Z və Vz ayrıca detal miqyasında qalır. Uzunluq, komponent üst-üstə göstərilməsi, mütləq mövqe xətası və eyni vəziyyətdə Ay həssaslığı ayrıca görünüşlərdə mövcuddur.",
    "OSCULATING KEPLER ELEMENTS — MODEL INITIAL / FINAL": "OSKULYASİYA KEPLER ELEMENTLƏRİ — MODEL İLKİN / FİNAL",
    "This dataset provides independent Moon-on and Moon-off reference cases. Select Moon and Sun in the force cards, then use the single RUN SELECTED action. Matching paired results are combined automatically; Sun-on results are reported as a sensitivity residual because the dataset has no solar case.": "Bu məlumat dəsti müstəqil Ay-aktiv və Ay-deaktiv referans hallarını təqdim edir. Qüvvə kartlarında Ay və Günəşi seçin, sonra SEÇİLMİŞ MODELİ İŞƏ SAL əmrinə basın. Uyğun cüt nəticələr avtomatik birləşdirilir; dəstdə Günəş halı olmadığı üçün Günəş-aktiv nəticələr həssaslıq residualı kimi göstərilir.",
    "This dataset provides only a WITH MOON reference series. The unavailable WITHOUT MOON scenario is disabled and no missing reference trajectory is synthesized. Sun β remains selectable for the available scenario.": "Bu məlumat dəsti yalnız AY İLƏ referans sırasını təqdim edir. Mövcud olmayan AYSIZ ssenari söndürülüb və çatışmayan referans trayektoriyası sintez edilmir. Mövcud ssenari üçün Günəş β seçilə bilər.",
    "EGM96 4×4 + physical, unmodified DE440 forces": "EGM96 4×4 + fiziki, dəyişdirilməmiş DE440 qüvvələri",
    "Two workflows. To check a bundled reference: pick it below and press RUN — leave the state fields empty and ignore the force switches, they do not affect that run. To predict from your own state: fill the J2000 fields, then press CALCULATE ECLIPSE EVENTS. Earth and Moon apparent discs are both evaluated.": "İki iş axını var. Daxili referansı yoxlamaq üçün aşağıdan seçib İŞƏ SAL düyməsinə basın — vəziyyət sahələrini boş saxlayın və qüvvə açarlarını nəzərə almayın; onlar bu hesablamaya təsir etmir. Öz vəziyyətinizdən proqnoz üçün J2000 sahələrini doldurun, sonra TUTULMA HADİSƏLƏRİNİ HESABLA düyməsinə basın. Yer və Ayın görünən diskləri birlikdə hesablanır.",
    "Earth EGM96 4×4": "Yer EGM96 4×4",
    "Research switches — both off reproduces the bundled references. Turning one on measures how much of a residual is convention rather than physics; it does not improve agreement.": "Tədqiqat açarları — hər ikisi sönülü olduqda daxili referanslar təkrarlanır. Birini aktiv etmək residualın nə qədərinin fizikadan deyil, konvensiyadan gəldiyini ölçür; uyğunluğu yaxşılaşdırmır.",
    "First scans at 1-hour intervals, then checks candidate days and four guard days on each side at 1-minute resolution. Days with no eclipse are listed as SKIPPED.": "Əvvəlcə 1 saatlıq intervallarla axtarır, sonra namizəd günləri və hər tərəfdə dörd qoruyucu günü 1 dəqiqəlik dəqiqliklə yoxlayır. Tutulma olmayan günlər KEÇİLDİ kimi göstərilir.",
    "Uses DE440 Sun direction and finite Earth/Sun apparent discs. Reference-range runs use the finite DE440 Moon disc as well. No artificial eclipse constant or copied contact time is used.": "DE440 Günəş istiqamətindən və sonlu Yer/Günəş görünən disklərindən istifadə edir. Referans intervalı hesablamalarında sonlu DE440 Ay diski də tətbiq olunur. Süni tutulma sabiti və ya kopyalanmış kontakt vaxtı istifadə edilmir.",
    "Enter an initial J2000 Cartesian state and propagate it with modular Earth EGM96, Moon, Sun third-body gravity and the selected spacecraft solar radiation pressure model.": "İlkin J2000 Dekart vəziyyətini daxil edin və onu modul Yer EGM96, Ay, Günəş üçüncü-cisim cazibəsi və seçilmiş kosmik aparatın günəş radiasiya təzyiqi modeli ilə propaqasiya edin.",
    "Coupled EGM96 degree/order supported by the existing gravity model.": "Mövcud cazibə modelinin dəstəklədiyi əlaqəli EGM96 dərəcə/tərtibi.",
    "Differential solar gravity from the DE440 Earth-to-Sun vector. This is separate from solar radiation pressure.": "DE440 Yer–Günəş vektorundan diferensial Günəş cazibəsi. Bu, Günəş radiasiya təzyiqindən ayrıdır.",
    "Show all six propagated J2000 Cartesian state components.": "Propaqasiya edilmiş altı J2000 Dekart vəziyyət komponentinin hamısını göstər.",
    "Loaded the selected public TLE state. TLE is an estimate; use a documented J2000 state for formal validation.": "Seçilmiş ictimai TLE vəziyyəti yükləndi. TLE təxminidir; formal yoxlama üçün sənədləşdirilmiş J2000 vəziyyətindən istifadə edin.",
    "Copied the Propagation input state. Eclipse calculation remains independent and will run only from this ECLIPSE tab.": "Propaqasiya giriş vəziyyəti kopyalandı. Tutulma hesablaması müstəqil qalır və yalnız bu TUTULMA səhifəsindən başladılır.",
    "Wait for Propagation to finish or cancel it first.": "Propaqasiyanın bitməsini gözləyin və ya əvvəlcə onu ləğv edin.",
    "Wait for Reference Lab calculation to finish or cancel it first.": "Referans Laboratoriyası hesablamasının bitməsini gözləyin və ya əvvəlcə onu ləğv edin.",
    "10-second steps are the precision default. Limb contacts are then refined to 1 ms inside each bracket.": "10 saniyəlik addım dəqiqlik standartıdır. Sonra kənar kontaktları hər intervalda 1 ms dəqiqliyə qədər təkmilləşdirilir.",
    "Minute steps are suitable for routine searches; use seconds for a denser illumination profile and tighter interpolation.": "Dəqiqəlik addımlar gündəlik axtarış üçün uyğundur; daha sıx işıqlanma profili və dəqiq interpolyasiya üçün saniyələrdən istifadə edin.",
    "Warning: hour/day search steps can skip an eclipse that falls completely between two samples.": "Xəbərdarlıq: saat/gün axtarış addımları iki nümunə arasına tam düşən tutulmanı ötürə bilər.",
    "YEAR CSV EXPORT ERROR\nRun the selected-year search first.": "İLLİK CSV İXRAC XƏTASI\nƏvvəlcə seçilmiş il axtarışını başladın.",
    "REFERENCE COMPARISON ERROR\nRun a normal or selected-year Eclipse calculation first.": "REFERANS MÜQAYİSƏ XƏTASI\nƏvvəlcə normal və ya seçilmiş il üzrə Tutulma hesablamasını başladın.",
    "REFERENCE CSV EXPORT ERROR\nRun the comparison first.": "REFERANS CSV İXRAC XƏTASI\nƏvvəlcə müqayisəni başladın.",
    "ECLIPSE CSV EXPORT ERROR\nCalculate eclipse events first.": "TUTULMA CSV İXRAC XƏTASI\nƏvvəlcə tutulma hadisələrini hesablayın.",
    "YEARLY ECLIPSE SEARCH CANCELLED\nNo partial schedule was stored.": "İLLİK TUTULMA AXTARIŞI LƏĞV EDİLDİ\nNatamam cədvəl saxlanılmadı.",
    "REFERENCE-RANGE SEARCH CANCELLED\nNo partial comparison was stored.": "REFERANS İNTERVALI AXTARIŞI LƏĞV EDİLDİ\nNatamam müqayisə saxlanılmadı.",
    "ECLIPSE CALCULATION CANCELLED\nNo partial result was stored.": "TUTULMA HESABLAMASI LƏĞV EDİLDİ\nNatamam nəticə saxlanılmadı.",
    "UPDATE DEGRADED": "YENİLƏNMƏ ZƏİFLƏYİB",
    "Project details": "Layihə məlumatları",
    "These fields are stored only in the .opa mission document. They do not change global application preferences.": "Bu sahələr yalnız .opa missiya sənədində saxlanılır. Qlobal tətbiq parametrlərini dəyişmir.",
    "The active profile supplies Propagation and GEO Operations inputs. Live Telemetry remains explicitly labelled SYNTHETIC GEO DEMO unless the validated built-in SYNTHETIC GEO DEMO profile is active.": "Aktiv profil Propaqasiya və GEO Əməliyyatları girişlərini təmin edir. Yoxlanmış daxili SYNTHETIC GEO DEMO profili aktiv olmadıqda Canlı Telemetriya açıq şəkildə SYNTHETIC GEO DEMO kimi göstərilməyə davam edir.",
    "Validated SYNTHETIC GEO DEMO physical box-wing SRP model with the explicit public-mode CP=1.0 coefficient.": "Açıq ictimai CP=1.0 əmsallı yoxlanmış SYNTHETIC GEO DEMO fiziki qutu-qanad SRP modeli.",
    "Analyze the latest propagated trajectory against an operator-defined longitude box and GEO element limits. Advisory estimates never alter the propagated state and are not flight-certified maneuver commands.": "Son propaqasiya trayektoriyasını operatorun təyin etdiyi uzunluq qutusu və GEO element limitləri ilə müqayisə edin. Məsləhət xarakterli qiymətləndirmələr propaqasiya vəziyyətini dəyişmir və uçuş üçün sertifikatlaşdırılmış manevr əmrləri deyil.",
    "Not configured": "Konfiqurasiya edilməyib",
    "GEO analysis report will appear here.": "GEO analiz hesabatı burada görünəcək.",
    "Satellite Profile Editor": "Peyk Profili Redaktoru",
    "Profiles provide validated spacecraft and mission inputs. They do not replace propagation or force-model equations.": "Profillər yoxlanmış kosmik aparat və missiya girişlərini təmin edir. Onlar propaqasiya və ya qüvvə-modeli tənliklərini əvəz etmir.",
    "TLE catalogue": "TLE kataloqu",
    "Cartesian J2000 state": "Dekart J2000 vəziyyəti",
    "Imported ephemeris state": "İdxal edilmiş efemerid vəziyyəti",
    "The current propagation backend accepts Earth-centred J2000/ICRF states.": "Cari propaqasiya mühərriki Yer-mərkəzli J2000/ICRF vəziyyətlərini qəbul edir.",
    "Catalogue/file source, generation method or operator provenance note": "Kataloq/fayl mənbəyi, yaratma üsulu və ya operator mənşə qeydi",
    "TrueSun tracking": "TrueSun izləmə",
    "Equivalent Sun-normal area": "Ekvivalent Günəş-normal sahə",
    "OPTICAL CONVENTION · For each surface: specular + diffuse + absorption = 1.0. Every coefficient must be dimensionless and in the inclusive range [0, 1]. Generic propagation uses the profile's equivalent area, mass and SRP coefficient; these surface shares remain explicit engineering metadata.": "OPTİK KONVENSİYA · Hər səth üçün: güzgü + diffuz + udulma = 1.0. Hər əmsal ölçüsüz və [0, 1] qapalı intervalında olmalıdır. Ümumi propaqasiya profilin ekvivalent sahə, kütlə və SRP əmsalından istifadə edir; səth payları açıq mühəndislik metaməlumatı kimi qalır.",
    "Satellite Profile Manager": "Peyk Profil Meneceri",
    "Built-in profiles are read-only. Duplicate one to create a validated operator-owned spacecraft configuration.": "Daxili profillər yalnız oxuma üçündür. Operatora məxsus yoxlanmış kosmik aparat konfiqurasiyası yaratmaq üçün onlardan birinin surətini çıxarın.",
    "Eccentricity warning [-]": "Eksentrisitet xəbərdarlığı [-]",
    "Duration [days]:": "Müddət [gün]:",
    "Step minutes:": "Addım dəqiqəsi:",
    "Step seconds:": "Addım saniyəsi:",
    "Earth harmonics:": "Yer harmonikləri:",
    "Include Earth EGM96 harmonics": "Yer EGM96 harmoniklərini daxil et",
    "Moon:": "Ay:",
    "Sun:": "Günəş:",
    "EGM96 degree/order 4 · active in reference runs": "EGM96 dərəcə/tərtib 4 · referans hesablamalarında aktivdir",
    "MOON THIRD-BODY": "AY ÜÇÜNCÜ CİSİM",
    "DE440 geometric J2000 · bundled 30-day references": "DE440 geometrik J2000 · daxili 30 günlük referanslar",
    "SUN THIRD-BODY": "GÜNƏŞ ÜÇÜNCÜ CİSİM",
    "READY / SELECTABLE": "HAZIR / SEÇİLƏ BİLƏR",
    "True of Date FK5 → J2000/ICRF after TOD axis rotation": "TOD ox fırlanmasından sonra tarixə uyğun FK5 → J2000/ICRF",
    "EGM96 4×4 + DE440 Moon": "EGM96 4×4 + DE440 Ay",
    "EARTH (MOON OFF) + WITH MOON": "YER (AY SÖNÜLÜ) + AY İLƏ",
    "READY — all available series passed integrity checks; 2 off-grid terminal row ignored": "HAZIR — bütün mövcud sıralar bütövlük yoxlamasından keçdi; şəbəkədənkənar 2 son sətir nəzərə alınmadı",
    "FINAL POSITION ERROR": "FİNAL MÖVQE XƏTASI",
    "Position residual at the final reference epoch": "Final referans epoxasındakı mövqe residualı",
    "RMS POSITION ERROR": "RMS MÖVQE XƏTASI",
    "Root-mean-square residual across the full trajectory": "Bütün trayektoriya üzrə orta kvadratik residual",
    "MAXIMUM POSITION ERROR": "MAKSİMUM MÖVQE XƏTASI",
    "Largest position residual over the validation interval": "Yoxlama intervalındakı ən böyük mövqe residualı",
    "FINAL VELOCITY ERROR": "FİNAL SÜRƏT XƏTASI",
    "Velocity residual at the final reference epoch": "Final referans epoxasındakı sürət residualı",
    "RUN SELECTED — EARTH + MOON": "SEÇİLMİŞİ İŞƏ SAL — YER + AY",
    "STATION BOX / LIMIT STATUS": "STANSİYA QUTUSU / LİMİT VƏZİYYƏTİ",
    "CURRENT GEO STATE": "CARİ GEO VƏZİYYƏTİ",
    "Auto Fit Selected": "Seçilmişə avtomatik uyğunlaşdır",
    "Satellite Close-up (1,000 km)": "Peyk yaxın görünüşü (1 000 km)",
    "Satellite Detail (100 km)": "Peyk detalı (100 km)",
    "Low Earth Orbit (12,000 km)": "Aşağı Yer orbiti (12 000 km)",
    "Earth-Moon System": "Yer–Ay sistemi",
    "Earth": "Yer",
    "EARTH + MOON": "YER + AY",
    "EARTH + SUN": "YER + GÜNƏŞ",
    "EARTH + MOON + SUN": "YER + AY + GÜNƏŞ",
    "EARTH + SRP (CP)": "YER + SRP (CP)",
    "EARTH + MOON + SRP (CP)": "YER + AY + SRP (CP)",
    "EARTH + SUN + SRP (CP)": "YER + GÜNƏŞ + SRP (CP)",
    "EARTH + MOON + SUN + SRP (CP)": "YER + AY + GÜNƏŞ + SRP (CP)",
    "Model №": "Model №",
    "Model input (UTC)": "Model girişi (UTC)",
    "Model output (UTC)": "Model çıxışı (UTC)",
    "Run validation to compare numerical propagation with the local TLE/SGP4 reference and estimate model sensitivities.": "Ədədi propaqasiyanı lokal TLE/SGP4 referansı ilə müqayisə etmək və model həssaslıqlarını qiymətləndirmək üçün yoxlamanı başladın.",
    "This user-supplied reference uses the force configuration declared in its manifest. Its CSV states are validated as an exact J2000/ICRF time grid before use.": "İstifadəçinin təqdim etdiyi bu referans manifestdə göstərilən qüvvə konfiqurasiyasından istifadə edir. CSV vəziyyətləri istifadədən əvvəl dəqiq J2000/ICRF zaman şəbəkəsi kimi yoxlanılır.",
    "Display name": "Görünən ad",
    "Operator": "Operator",
    "Notes": "Qeydlər",
    "Orbit source": "Orbit mənbəyi",
    "TLE name": "TLE adı",
    "Cartesian epoch UTC": "Dekart epoxası UTC",
    "Reference frame": "Referans çərçivəsi",
    "Source / provenance": "Mənbə / mənşə",
    "Ephemeris import": "Efemerid idxalı",
    "Total mass [kg]": "Ümumi kütlə [kg]",
    "Dry mass [kg]": "Quru kütlə [kg]",
    "Propellant [kg]": "Yanacaq [kg]",
    "Thruster Isp [s]": "Mühərrik Isp [s]",
    "Body X [m]": "Gövdə X [m]",
    "Body Y [m]": "Gövdə Y [m]",
    "Body Z [m]": "Gövdə Z [m]",
    "Array count": "Panel sayı",
    "Array orientation": "Panel orientasiyası",
    "Array width [m]": "Panel eni [m]",
    "Array height [m]": "Panel hündürlüyü [m]",
    "Body specular": "Gövdə güzgü əmsalı",
    "Body diffuse": "Gövdə diffuz əmsalı",
    "Body absorption": "Gövdə udulma əmsalı",
    "SRP coefficient": "SRP əmsalı",
    "Array specular": "Panel güzgü əmsalı",
    "Array diffuse": "Panel diffuz əmsalı",
    "Array absorption": "Panel udulma əmsalı",
    "Target longitude [deg E]": "Hədəf uzunluq [dərəcə E]",
    "Station half-width [deg]": "Stansiya yarımeni [dərəcə]",
    "Inclination warning [deg]": "Meyillik xəbərdarlığı [dərəcə]",
    "Inclination limit [deg]": "Meyillik limiti [dərəcə]",
    "Eccentricity warning": "Eksentrisitet xəbərdarlığı",
    "Eccentricity limit": "Eksentrisitet limiti",
    "Annual ΔV budget [m/s]": "İllik ΔV büdcəsi [m/s]",
    "Open OPA project": "OPA layihəsini aç",
    "Save OPA project": "OPA layihəsini yadda saxla",
    "Import J2000 ephemeris state": "J2000 efemerid vəziyyətini idxal et",
    "Import satellite profile": "Peyk profilini idxal et",
    "Export satellite profile": "Peyk profilini ixrac et",
    "Export Reference Model CSV": "Referans model CSV-sini ixrac et",
    "Save Propagation Output": "Propaqasiya nəticəsini yadda saxla",
    "Save Propagation CSV": "Propaqasiya CSV-sini yadda saxla",
    "Export Yearly Eclipse Schedule CSV": "İllik tutulma cədvəli CSV-sini ixrac et",
    "Export Eclipse Reference Comparison CSV": "Tutulma referans müqayisəsi CSV-sini ixrac et",
    "Export Eclipse Timeline and Events CSV": "Tutulma zaman xətti və hadisələr CSV-sini ixrac et",
    "Invalid satellite profile": "Peyk profili etibarsızdır",
    "Ephemeris import failed": "Efemerid idxalı alınmadı",
    "Profile save failed": "Profilin yadda saxlanması alınmadı",
    "Built-in profile": "Daxili profil",
    "Duplicate this profile before editing it.": "Redaktə etməzdən əvvəl bu profilin surətini çıxarın.",
    "Built-in profiles cannot be deleted.": "Daxili profillər silinə bilməz.",
    "Delete satellite profile": "Peyk profilini sil",
    "Profile delete failed": "Profilin silinməsi alınmadı",
    "Profile import failed": "Profil idxalı alınmadı",
    "Profile export failed": "Profil ixracı alınmadı",
    "Project name": "Layihənin adı",
    "Description": "Təsvir",
    "Mission notes": "Missiya qeydləri",
    "Project name is required.": "Layihənin adı tələb olunur.",
    "Profile activation failed": "Profilin aktivləşdirilməsi alınmadı",
    "Unsaved project changes": "Yadda saxlanılmamış layihə dəyişiklikləri",
    "The current project has unsaved changes. Save before continuing?": "Cari layihədə yadda saxlanılmamış dəyişikliklər var. Davam etməzdən əvvəl yadda saxlansın?",
    "Recent project unavailable": "Son layihə əlçatan deyil",
    "Project open failed": "Layihənin açılması alınmadı",
    "Project profile snapshot": "Layihə profilinin ani görüntüsü",
    "Project save failed": "Layihənin yadda saxlanması alınmadı",
    "Scrolls the page by default. Click the graph to enable wheel zoom; click outside the graph to return the wheel to page scrolling.": "Standart olaraq səhifəni sürüşdürür. Çarxla miqyası aktiv etmək üçün qrafikə klikləyin; səhifə sürüşdürməsinə qayıtmaq üçün qrafikdən kənara klikləyin.",
}


# Ordered fragments cover dynamic status strings that contain dates, values or
# object names and therefore cannot be represented by an exact dictionary key.
AZ_PHRASE_TRANSLATIONS = (
    ("SESSION CONTENT —", "SESSİYA MƏZMUNU —"),
    ("profiles ·", "profil ·"),
    ("references ·", "referans ·"),
    ("data-only modules", "yalnız məlumat modulu"),
    ("Measurements in selected arc:", "Seçilmiş intervaldakı ölçmələr:"),
    ("reference discontinuities:", "referans kəsilmələri:"),
    ("Measurements:", "Ölçmələr:"),
    ("Reference orbit:", "Referans orbit:"),
    ("discontinuities:", "kəsilmələr:"),
    ("Frame:", "Çərçivə:"),
    ("PREFIT PROPAGATION", "İLKİN PROPAQASİYA"),
    ("POSTFIT PROPAGATION", "SON PROPAQASİYA"),
    ("REFERENCE VALIDATION", "REFERANS YOXLAMASI"),
    ("LINE SEARCH", "ADDIM AXTARIŞI"),
    ("JACOBIAN", "YAKOBİAN"),
    ("ITERATION", "İTERASİYA"),
    ("WEIGHTED LEAST SQUARES COMPLETED", "ÇƏKİLİ ƏN KİÇİK KVADRATLAR TAMAMLANDI"),
    ("STARTING WEIGHTED LEAST SQUARES", "ÇƏKİLİ ƏN KİÇİK KVADRATLAR BAŞLAYIR"),
    ("Manual combined effective-area model", "Əl ilə ümumi effektiv-sahə modeli"),
    ("Manual panel + body force sum", "Əl ilə panel + gövdə qüvvə cəmi"),
    ("Manual panel/body SRP", "Əl ilə panel/gövdə SRP-si"),
    ("Manual combined effective-area SRP", "Əl ilə ümumi effektiv-sahə SRP-si"),
    ("equivalent area", "ekvivalent sahə"),
    ("equivalent CP", "ekvivalent CP"),
    (" + body ", " + gövdə "),
    (" · body ", " · gövdə "),
    (" · area ", " · sahə "),
    ("Earth umbra/penumbra", "Yer tam/yarımkölgəsi"),
    ("Configuration save failed:", "Konfiqurasiyanın yadda saxlanması alınmadı:"),
    ("Save failed:", "Yadda saxlama alınmadı:"),
    ("Tolerances must be positive.", "Dözümlülük qiymətləri müsbət olmalıdır."),
    ("Unknown interface theme selection.", "Naməlum interfeys mövzusu seçimi."),
    ("Unknown language selection.", "Naməlum dil seçimi."),
    ("TLE STATUS: CURRENT", "TLE STATUSU: CARİ"),
    ("USER REFERENCE SCAN —", "İSTİFADƏÇİ REFERANSI AXTARIŞI —"),
    ("USER REFERENCES —", "İSTİFADƏÇİ REFERANSLARI —"),
    ("USER REFERENCE —", "İSTİFADƏÇİ REFERANSI —"),
    ("Reference folder opened:", "Referans qovluğu açıldı:"),
    ("Reference folder could not be opened:", "Referans qovluğunu açmaq alınmadı:"),
    ("Reference scan complete:", "Referans axtarışı tamamlandı:"),
    ("validated and loaded", "yoxlanıldı və yükləndi"),
    ("loaded,", "yükləndi,"),
    ("rejected:", "qəbul edilmədi:"),
    ("rejected.", "qəbul edilmədi."),
    ("none found; use the folder guide and", "tapılmadı; qovluqdakı təlimat və"),
    ("template", "şablondan istifadə edin"),
    ("This user-supplied reference uses the force configuration declared in its manifest.", "İstifadəçinin təqdim etdiyi bu referans manifestdə göstərilən qüvvə konfiqurasiyasından istifadə edir."),
    ("This user-supplied reference was discovered from a validated opa-reference/v1 manifest.", "İstifadəçinin təqdim etdiyi bu referans yoxlanmış opa-reference/v1 manifestindən aşkarlandı."),
    ("Declared force model:", "Göstərilən qüvvə modeli:"),
    ("Its CSV states use an exact J2000/ICRF time grid; unsupported or ambiguous files are not registered.", "Onun CSV vəziyyətləri dəqiq J2000/ICRF zaman şəbəkəsindən istifadə edir; dəstəklənməyən və ya qeyri-müəyyən fayllar qeydiyyata alınmır."),
    ("Its SRP parameters are area", "Onun SRP parametrləri: sahə"),
    ("mass", "kütlə"),
    ("and coefficient", "və əmsal"),
    ("The CSV states are validated as an exact J2000/ICRF time grid before use.", "CSV vəziyyətləri istifadədən əvvəl dəqiq J2000/ICRF zaman şəbəkəsi kimi yoxlanılır."),
    ("TLE: CURRENT", "TLE: CARİ"),
    ("EOP ACTIVE", "EOP AKTİVDİR"),
    ("FORCE MODEL UPDATED", "QÜVVƏ MODELİ YENİLƏNDİ"),
    ("Press RUN SELECTED MODEL to execute this exact configuration.", "Bu konfiqurasiyanı işə salmaq üçün SEÇİLMİŞ MODELİ İŞƏ SAL düyməsinə basın."),
    ("Satellite:", "Peyk:"),
    ("Epoch:", "Epoxa:"),
    ("Age:", "Yaş:"),
    ("Local file:", "Lokal fayl:"),
    ("Source:", "Mənbə:"),
    ("Current:", "Cari:"),
    ("Coverage:", "Əhatə:"),
    ("active satellites", "aktiv peyklər"),
    ("local cache", "lokal keş"),
    ("SPICE kernels", "SPICE nüvələri"),
    ("daily rows", "gündəlik sətir"),
    ("Earth-centred inertial", "Yer-mərkəzli ətalət"),
    ("Earth-centred", "Yer-mərkəzli"),
    ("Numerical propagator:", "Ədədi propaqator:"),
    ("geometric", "geometrik"),
    ("FOCUS: EARTH", "FOKUS: YER"),
    ("EARTH X:", "YER X:"),
    ("EARTH", "YER"),
    ("MOON", "AY"),
    ("SUN", "GÜNƏŞ"),
    ("FITTED", "UYĞUNLAŞDIRILMIŞ"),
    ("Moon: SPICE", "Ay: SPICE"),
    ("DE440 Moon", "DE440 Ay"),
    ("J2000-aligned", "J2000 ilə uyğun"),
    ("(NONE)", "(YOXDUR)"),
    ("VIEW METRICS", "GÖRÜNÜŞ METRİKLƏRİ"),
    ("Selected:", "Seçilmiş:"),
    ("Span:", "Aralıq:"),
    ("Degree/order", "Dərəcə/tərtib"),
    ("MULTI-BODY DYNAMICS CONSOLE", "ÇOXCİSİMLİ DİNAMİKA KONSOLU"),
    ("LIVE / PROPAGATION / GEO", "CANLI / PROPAQASİYA / GEO"),
    ("PROPAGATION / GEO PROFILE", "PROPAQASİYA / GEO PROFİLİ"),
    ("LIVE TLE SATELLITE", "CANLI TLE PEYKİ"),
    ("NOMINAL / UNCALIBRATED", "NOMİNAL / KALİBRLƏNMƏMİŞ"),
    (" · BUILT-IN", " · DAXİLİ"),
    (" · PROJECT SNAPSHOT", " · LAYİHƏ ANI GÖRÜNTÜSÜ"),
    ("  ·  BUILT-IN", "  ·  DAXİLİ"),
    ("  ·  USER", "  ·  İSTİFADƏÇİ"),
    ("  ·  ACTIVE", "  ·  AKTİV"),
    ("BUILT-IN / READ-ONLY", "DAXİLİ / YALNIZ OXUMA"),
    ("Bundled local TLE catalogue; validated SYNTHETIC GEO DEMO baseline.", "Daxili lokal TLE kataloqu; yoxlanmış SYNTHETIC GEO DEMO baza xətti."),
    ("Immutable validated application baseline.", "Dəyişməz yoxlanmış tətbiq baza xətti."),
    ("Imported ephemeris", "İdxal edilmiş efemerid"),
    ("Manual Cartesian", "Əl ilə daxil edilmiş Dekart"),
    ("Earth gravity    : REQUIRED", "Yer cazibəsi    : TƏLƏB OLUNUR"),
    ("Moon ON", "Ay AKTİVDİR"),
    ("Moon OFF", "Ay SÖNÜLÜDÜR"),
    ("Sun ON", "Günəş AKTİVDİR"),
    ("Sun OFF", "Günəş SÖNÜLÜDÜR"),
    ("SRP ON", "SRP AKTİVDİR"),
    ("SRP OFF", "SRP SÖNÜLÜDÜR"),
    ("EOP ON", "EOP AKTİVDİR"),
    ("EOP OFF", "EOP SÖNÜLÜDÜR"),
    ("Profile ID", "Profil ID"),
    ("Ownership", "Mülkiyyət"),
    ("Orbit source", "Orbit mənbəyi"),
    ("Provenance", "Mənşə"),
    ("Mass", "Kütlə"),
    ("Solar-array area", "Günəş paneli sahəsi"),
    ("Array mode", "Panel rejimi"),
    ("Earth gravity", "Yer cazibəsi"),
    ("Force defaults", "Qüvvə standartları"),
    ("GEO target", "GEO hədəfi"),
    ("No profile notes.", "Profil qeydi yoxdur."),
    ("Delete '", "Silinsin: '"),
    ("This cannot be undone.", "Bu əməliyyat geri qaytarıla bilməz."),
    ("The project no longer exists at:", "Layihə artıq bu ünvanda mövcud deyil:"),
    ("Loaded profile into propagation:", "Profil propaqasiya girişinə yükləndi:"),
    ("Profile state could not be loaded:", "Profil vəziyyətini yükləmək alınmadı:"),
    ("Saved project:", "Layihə yadda saxlanıldı:"),
    ("Project opened; recent list could not be saved:", "Layihə açıldı; son layihələr siyahısını yadda saxlamaq alınmadı:"),
    ("Project saved; recent list could not be saved:", "Layihə yadda saxlanıldı; son layihələr siyahısını yadda saxlamaq alınmadı:"),
    ("The application is restarting with the new configuration...", "Tətbiq yeni konfiqurasiya ilə yenidən başladılır..."),
    ("REFRESH is waiting: stop the active calculation first", "YENİDƏN BAŞLATMA gözləyir: əvvəlcə aktiv hesablamanı dayandırın"),
    ("Remaining: estimating…", "Qalan vaxt: hesablanır…"),
    ("Remaining:", "Qalan vaxt:"),
    ("Range changed.", "İnterval dəyişdi."),
    ("Force selection changed.", "Qüvvə seçimi dəyişdi."),
    ("Calculating perturbation prediction in the background...", "Perturbasiya proqnozu arxa planda hesablanır..."),
    ("Cancelling perturbation prediction...", "Perturbasiya proqnozu ləğv edilir..."),
    ("Perturbation prediction cancelled.", "Perturbasiya proqnozu ləğv edildi."),
    ("Prediction setup error:", "Proqnoz hazırlığı xətası:"),
    ("Prediction error:", "Proqnoz xətası:"),
    ("prediction ready:", "proqnozu hazırdır:"),
    ("points with numerical sensitivity band.", "ədədi həssaslıq zolaqlı nöqtə."),
    ("Scroll to explore.", "Baxmaq üçün sürüşdürün."),
    ("Run prediction", "Proqnozu başladın"),
    ("Run the selected-year search first.", "Əvvəlcə seçilmiş il axtarışını başladın."),
    ("Calculate eclipse events first.", "Əvvəlcə tutulma hadisələrini hesablayın."),
    ("Run the comparison first.", "Əvvəlcə müqayisəni başladın."),
    ("No eclipse events in this search window", "Bu axtarış intervalında tutulma hadisəsi yoxdur"),
    ("CALCULATION CANCELLED", "HESABLAMA LƏĞV EDİLDİ"),
    ("SEARCH CANCELLED", "AXTARIŞ LƏĞV EDİLDİ"),
    ("EXPORT ERROR", "İXRAC XƏTASI"),
    ("ERROR", "XƏTA"),
    ("CANCELLED", "LƏĞV EDİLDİ"),
    ("Waiting for", "Gözlənilir:"),
    ("Loading", "Yüklənir"),
    ("Downloading and validating", "Endirilir və yoxlanılır"),
    ("Selected interval:", "Seçilmiş interval:"),
    ("fixed geostationary slot", "sabit geostasionar mövqe"),
    ("the 'Events from: Nominal Orbit' model in the reference file", "referans faylındakı 'Events from: Nominal Orbit' modeli"),
    ("Reference:", "Referans:"),
    ("Satellite sources:", "Peyk mənbələri:"),
    ("from companion source", "yanaşı mənbədən"),
    ("Model:", "Model:"),
    ("Mean absolute error:", "Orta mütləq xəta:"),
    ("Maximum error:", "Ən böyük xəta:"),
    ("Exact difference:", "Dəqiq fərq:"),
    ("(model − reference)", "(model − referans)"),
    ("Each 1 millidegree geometry difference shifts contact time by", "Həndəsədə hər 1 millidərəcə fərq kontakt vaxtını bu qədər sürüşdürür:"),
    ("The satellite grazes the shadow edge, so a large difference is expected here and is not a model defect.", "Peyk kölgənin kənarına toxunaraq keçir; buna görə burada böyük fərq gözlənilir və bu, model qüsuru deyil."),
    ("RESULT:", "NƏTİCƏ:"),
    ("The time direction could not be determined.", "Vaxt istiqaməti müəyyən edilə bilmədi."),
    ("On average, the model finds the Eclipse", "Model tutulmanı orta hesabla"),
    ("MAIN CAUSE:", "ƏSAS SƏBƏB:"),
    ("SOLUTION:", "HƏLL:"),
    ("MODEL SOURCE:", "MODEL MƏNBƏYİ:"),
    ("Mean absolute error:", "Orta mütləq xəta:"),
    ("Maximum error:", "Ən böyük xəta:"),
    (" matching,", " uyğun,"),
    (" different times,", " fərqli vaxt,"),
    (" missing model outputs,", " çatışmayan model nəticəsi,"),
    (" extra events.", " artıq hadisə."),
    (" early", " tez"),
    (" late", " gec"),
    (" shorter", " qısa"),
    (" longer", " uzun"),
    ("seconds", "saniyə"),
    ("minutes", "dəqiqə"),
    ("hours", "saat"),
    ("days", "gün"),
)


def translate_text(text, language):
    """Translate one user-facing string while preserving scientific tokens."""

    if not isinstance(text, str) or not text or normalise_language(language) == "en":
        return text
    exact = AZ_TRANSLATIONS.get(text)
    if exact is not None:
        return exact
    translated = text
    for source, target in AZ_PHRASE_TRANSLATIONS:
        translated = translated.replace(source, target)
    return translated


def _translate_object_text(obj, key, getter, setter, language):
    """Translate a QObject string property and retain its canonical source."""

    current = getter()
    source_key = f"opa_i18n_source_{key}"
    last_key = f"opa_i18n_last_{key}"
    source = obj.property(source_key)
    last = obj.property(last_key)
    if source is None or current != last:
        source = current
        obj.setProperty(source_key, source)
    translated = translate_text(source, language)
    if current != translated:
        setter(translated)
    obj.setProperty(last_key, translated)


def _translate_combo(combo, language):
    sources = combo.property("opa_i18n_combo_sources")
    previous = combo.property("opa_i18n_combo_last")
    if not isinstance(sources, list):
        sources = []
    if not isinstance(previous, list):
        previous = []
    updated_sources = []
    updated_last = []
    combo.blockSignals(True)
    try:
        for index in range(combo.count()):
            current = combo.itemText(index)
            source = sources[index] if index < len(sources) else current
            last = previous[index] if index < len(previous) else None
            if current != last:
                source = current
            translated = translate_text(source, language)
            if current != translated:
                combo.setItemText(index, translated)
            updated_sources.append(source)
            updated_last.append(translated)
    finally:
        combo.blockSignals(False)
    combo.setProperty("opa_i18n_combo_sources", updated_sources)
    combo.setProperty("opa_i18n_combo_last", updated_last)


def _translate_tabs(tabs, language):
    sources = tabs.property("opa_i18n_tab_sources")
    previous = tabs.property("opa_i18n_tab_last")
    if not isinstance(sources, list):
        sources = []
    if not isinstance(previous, list):
        previous = []
    updated_sources = []
    updated_last = []
    for index in range(tabs.count()):
        current = tabs.tabText(index)
        source = sources[index] if index < len(sources) else current
        last = previous[index] if index < len(previous) else None
        if current != last:
            source = current
        translated = translate_text(source, language)
        if current != translated:
            tabs.setTabText(index, translated)
        updated_sources.append(source)
        updated_last.append(translated)
    tabs.setProperty("opa_i18n_tab_sources", updated_sources)
    tabs.setProperty("opa_i18n_tab_last", updated_last)


_ITEM_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 73
_ITEM_LAST_ROLE = int(Qt.ItemDataRole.UserRole) + 74


def _translate_item(item, language):
    if item is None:
        return
    current = item.text()
    source = item.data(_ITEM_SOURCE_ROLE)
    last = item.data(_ITEM_LAST_ROLE)
    if source is None or current != last:
        source = current
        item.setData(_ITEM_SOURCE_ROLE, source)
    translated = translate_text(source, language)
    if current != translated:
        item.setText(translated)
    item.setData(_ITEM_LAST_ROLE, translated)


def _translate_table(table, language):
    for column in range(table.columnCount()):
        _translate_item(table.horizontalHeaderItem(column), language)
    for row in range(table.rowCount()):
        _translate_item(table.verticalHeaderItem(row), language)
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None and any(character.isalpha() for character in item.text()):
                _translate_item(item, language)


def _translate_matplotlib(widget, language):
    figure = getattr(widget, "figure", None)
    if figure is None or not hasattr(figure, "axes"):
        return False
    changed = False
    artists = []
    for axis in figure.axes:
        artists.extend((axis.title, axis.xaxis.label, axis.yaxis.label))
        artists.extend(axis.texts)
        legend = axis.get_legend()
        if legend is not None:
            artists.extend(legend.get_texts())
    for artist in artists:
        current = artist.get_text()
        source = getattr(artist, "_opa_i18n_source", None)
        last = getattr(artist, "_opa_i18n_last", None)
        if source is None or current != last:
            source = current
            artist._opa_i18n_source = source
        translated = translate_text(source, language)
        if current != translated:
            artist.set_text(translated)
            changed = True
        artist._opa_i18n_last = translated
    return changed


def translate_widget_tree(
    root,
    language,
    *,
    include_matplotlib=True,
    include_table_cells=True,
):
    """Translate all current and future-facing text below ``root``.

    The function is safe to call repeatedly.  Dynamic labels are detected when
    their canonical text changes, while already translated text is skipped.
    """

    language = normalise_language(language)
    if isinstance(root, QApplication):
        roots = list(root.topLevelWidgets())
    elif isinstance(root, QWidget):
        roots = [root]
    else:
        return language

    for top_level in roots:
        widgets = [top_level, *top_level.findChildren(QWidget)]
        redraw = []
        for widget in widgets:
            _translate_object_text(
                widget,
                "tooltip",
                widget.toolTip,
                widget.setToolTip,
                language,
            )
            _translate_object_text(
                widget,
                "status_tip",
                widget.statusTip,
                widget.setStatusTip,
                language,
            )
            _translate_object_text(
                widget,
                "window_title",
                widget.windowTitle,
                widget.setWindowTitle,
                language,
            )
            if isinstance(widget, QGroupBox):
                _translate_object_text(
                    widget,
                    "title",
                    widget.title,
                    widget.setTitle,
                    language,
                )
            if isinstance(widget, (QLabel, QAbstractButton)):
                _translate_object_text(
                    widget,
                    "text",
                    widget.text,
                    widget.setText,
                    language,
                )
            if isinstance(widget, QLineEdit):
                _translate_object_text(
                    widget,
                    "placeholder",
                    widget.placeholderText,
                    widget.setPlaceholderText,
                    language,
                )
            if isinstance(widget, (QTextEdit, QPlainTextEdit)) and widget.isReadOnly():
                _translate_object_text(
                    widget,
                    "plain_text",
                    widget.toPlainText,
                    widget.setPlainText,
                    language,
                )
            if isinstance(widget, QComboBox):
                _translate_combo(widget, language)
            if isinstance(widget, QTabWidget):
                _translate_tabs(widget, language)
            if isinstance(widget, QTableWidget):
                if include_table_cells:
                    _translate_table(widget, language)
                else:
                    # Periodic translation refreshes only need table headings.
                    # Walking every result cell becomes very expensive after a
                    # large propagation or OD result has been displayed.
                    for column in range(widget.columnCount()):
                        _translate_item(widget.horizontalHeaderItem(column), language)
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                _translate_object_text(
                    widget,
                    "prefix",
                    widget.prefix,
                    widget.setPrefix,
                    language,
                )
                _translate_object_text(
                    widget,
                    "suffix",
                    widget.suffix,
                    widget.setSuffix,
                    language,
                )
            if (
                include_matplotlib
                and _translate_matplotlib(widget, language)
                and widget.isVisible()
            ):
                redraw.append(widget)
        for action in top_level.findChildren(QAction):
            _translate_object_text(
                action,
                "text",
                action.text,
                action.setText,
                language,
            )
            _translate_object_text(
                action,
                "tooltip",
                action.toolTip,
                action.setToolTip,
                language,
            )
            _translate_object_text(
                action,
                "status_tip",
                action.statusTip,
                action.setStatusTip,
                language,
            )
        for widget in redraw:
            canvas = getattr(widget, "canvas", widget)
            draw_idle = getattr(canvas, "draw_idle", None)
            if callable(draw_idle):
                draw_idle()
        top_level.setProperty("opa_language", language)
    return language


def show_localized_message(
    parent,
    icon,
    title,
    text,
    buttons=QMessageBox.StandardButton.Ok,
    default_button=QMessageBox.StandardButton.NoButton,
):
    """Show a QMessageBox whose title, body and standard buttons match the UI."""

    message_box = QMessageBox(icon, title, text, buttons, parent)
    if default_button != QMessageBox.StandardButton.NoButton:
        message_box.setDefaultButton(default_button)
    translate_widget_tree(message_box, language_for_widget(parent))
    return QMessageBox.StandardButton(message_box.exec())
