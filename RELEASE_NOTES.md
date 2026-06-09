# Air Cooler Main - v3.7.1 Release Notes

Doğal gaz ve hidrokarbon karışımları için çapraz akışlı gaz soğutucu termal yük, boyutlandırma ve değerlendirme hesaplayıcısının **v3.7.1** sürümünü duyurmaktan mutluluk duyarız! Bu güncelleme, **v3.7.0**'ın kararlılık ve kullanıcı deneyimi iyileştirme sürümüdür.

---

## 🚀 Yeni Özellikler ve İyileştirmeler

### 1. Düzenlenebilir Karışım Tablosu (Editable Composition Table)
*   **Mevcut karışım tablosundaki yüzde değerleri** artık doğrudan sayı girişi ile düzenlenebilir. Her bileşen satırında bir `number_input` bulunur.
*   **4 ondalık haneli hassasiyet** (`%.4f`) ile hem giriş hem görüntüleme yapılır.
*   Kullanıcı, bileşen eklemeden mevcut yüzdeleri ince ayar yaparak değiştirebilir.

### 2. Akıllı Normalizasyon Sistemi (%99 Eşiği)
*   Bileşen toplamı **%99.00 veya üzeri** olduğunda, otomatik normalize edilerek hesaplamaya izin verilir.
*   Toplam %99.00'ın altındaysa kullanıcıya uyarı gösterilir.
*   Normalize edilen her hesaplama için `ara_sonuclar["normalize_edildi"]` flag'i eklenir.

### 3. CoolProp Fluid Adı Düzeltmesi
*   `COOLPROP_COMPONENTS` sözlüğünde `"I-BUTANE"` → `"ISOBUTANE"`, `"I-PENTANE"` → `"ISOPENTANE"` olarak düzeltildi.
*   **Geriye dönük uyumluluk:** Eski adlar (`"I-BUTANE"`, `"I-PENTANE"`) için `COOLPROP_ALIASES` haritası eklendi. Eski şablon/config dosyalarından gelen hatalı isimler otomatik çözümlenir.
*   `_init_abstract_state`, `get_mixture_transport_properties`, `_kutlesel_mol_cevir` fonksiyonları alias üzerinden çalışır.

### 4. Bağımlılık Yönetimi ve Test Kalitesi
*   `requirements.txt`'ye eksik bağımlılıklar (`ht`, `fluids`, `scipy`) eklendi.
*   `air_cooler_main_app.py`'ye `import ht` eklendi.
*   PyInstaller spec hidden imports güncellendi.
*   **8 yeni test** ile toplam 34 teste ulaşıldı, coverage %93.

---

## 📦 Dağıtım Paketleri ve Kurulum Talimatları

### 1. Windows Kurulumu (`AirCooler_Main-v3.7.1-windows-x64.zip`)
1.  İndirdiğiniz `.zip` dosyasını bir klasöre çıkartın.
2.  Klasör içerisindeki `AirCooler_Main.exe` dosyasını çift tıklayarak çalıştırın.
    > [!IMPORTANT]
    > `AirCooler_Main.exe` dosyasının çalışabilmesi için klasördeki `_internal` dizininin silinmemesi ve aynı dizinde bulunması gerekmektedir.

    > [!WARNING]
    > **Windows SmartScreen Uyarısı Çıkarsa:**
    > Lisanslı dijital sertifika imzası içermeyen bağımsız projelerde Windows *"Windows kişisel bilgisayarınızı korudu"* uyarısı verebilir. Bunu aşmak için ekrandaki **Ek Bilgi (More Info)** seçeneğine ve ardından beliren **Yine de Çalıştır (Run Anyway)** butonuna basabilirsiniz.

### 2. macOS Kurulumu (`AirCooler_Main-v3.7.1-macos-arm64.dmg`)
1.  İndirdiğiniz `.dmg` dosyasına çift tıklayarak mount edin.
2.  Klasör içerisindeki `AirCooler_Main` çalıştırılabilir dosyasını çalıştırın veya uygulamanızı bilgisayarınıza kopyalayın.

    > [!WARNING]
    > **macOS Kötü Amaçlı Yazılım / Güvenlik Uyarısı (Gatekeeper Bypass):**
    > Apple Developer sertifikası ile imzalanmamış açık kaynaklı projelerde macOS ilk çalıştırmada *"Apple, kötü amaçlı yazılım içermediğini doğrulayamadı..."* uyarısı verir. Bu güvenlik engelini aşmak için:
    > 1. Klasördeki `AirCooler_Main` dosyasına **sağ tıklayıp (Control tuşuna basılı tutarak) Aç (Open)** seçeneğini seçin. Karşınıza gelen onay penceresinde **Aç (Open)** butonuna tıklayın.
    > 2. Veya Mac'inizde **Sistem Ayarları > Gizlilik ve Güvenlik** menüsüne girin. Sayfanın en altındaki *"Yine de Aç (Open Anyway)"* butonuna tıklayın.
    > 3. Alternatif olarak, Terminal'i açıp şu komutu çalıştırarak karantina etiketini kaldırabilirsiniz:
    >    ```bash
    >    xattr -cr /path/to/AirCooler_Main
    >    ```

### Varsayılan Giriş Bilgileri (Default Credentials)
İlk açılışta veritabanı otomatik olarak kurulur ve aşağıdaki varsayılan kullanıcılar oluşturulur:
*   **Yönetici (Admin):** Kullanıcı adı: `admin` | Şifre: `admin123`
*   **Standart Kullanıcı (User):** Kullanıcı adı: `user` | Şifre: `user123`

---

## 🔒 Güvenlik & Dosya Doğrulama (Checksums)

İndirdiğiniz dosyaların bütünlüğünü ve güvenliğini doğrulamak için aşağıdaki SHA-256 değerlerini kontrol edebilirsiniz:

| Dosya Adı | Platform | SHA-256 Değeri |
| :--- | :--- | :--- |
| `AirCooler_Main-v3.7.1-macos-arm64.dmg` | macOS (Apple Silicon) | `a085c9fbf7164867609d1ae1a279b3370ef35fdec2944963ea5fac47acbd22ee` |
| `AirCooler_Main-v3.7.1-windows-x64.zip` | Windows (x64) | *Windows ortamında derlendiğinde hesaplanacaktır* |
