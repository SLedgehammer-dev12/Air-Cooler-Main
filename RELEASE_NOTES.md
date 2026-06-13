# Air Cooler Main - v3.7.2 Hotfix Release

Doğal gaz ve hidrokarbon karışımları için çapraz akışlı gaz soğutucu termal yük, boyutlandırma ve değerlendirme hesaplayıcısının **v3.7.2** sürümünü duyurmaktan mutluluk duyarız! Bu güncelleme, **v3.7.1** sürümüne küçük iyileştirmeler ve hata düzeltmeleri getirir.

---

## 🚀 Yeni Özellikler ve İyileştirmeler

### 1. Proje Kaydet / Aç Özelliği (Save/Load)
*   **💾 Kaydet:** Tüm girdiler (kompozisyon, proses şartları, geometri, birim seçimi) JSON formatında dışa aktarılabilir.
*   **📂 Aç:** Kaydedilen JSON proje dosyası yüklenerek tüm girdiler otomatik olarak geri yüklenir.
*   **Toolbar:** Girişler sekmesinin üst kısmında "💾 Kaydet" ve "📂 Aç" butonları yerleştirildi.

### 2. Test Kapsamı Artışı
*   **Yeni testler:** neqsim fallback zinciri, transport properties hata yönetimi, benchmark performans eşiği.
*   **Kapsam:** Core modülünde **%96**'ya (toplamda **%93**'e) ulaşıldı.
*   **Toplam test sayısı:** 136'ya yükseldi.

### 3. Performans Eşiği Testi
*   Benchmark testlerine mutlak performans eşiği eklendi.
*   **HEOS** < 200ms, **GERG-2008** < 500ms, **PR/SRK** < 20ms eşik değerleri tanımlandı.

---

## 📦 Dağıtım Paketleri ve Kurulum Talimatları

### 1. Windows Kurulumu (`AirCooler_Main-v3.7.2-windows-x64.zip`)
1.  İndirdiğiniz `.zip` dosyasını bir klasöre çıkartın.
2.  Klasör içerisindeki `AirCooler_Main.exe` dosyasını çift tıklayarak çalıştırın.
    > [!IMPORTANT]
    > `AirCooler_Main.exe` dosyasının çalışabilmesi için klasördeki `_internal` dizininin silinmemesi ve aynı dizinde bulunması gerekmektedir.

    > [!WARNING]
    > **Windows SmartScreen Uyarısı Çıkarsa:**
    > Lisanslı dijital sertifika imzası içermeyen bağımsız projelerde Windows *"Windows kişisel bilgisayarınızı korudu"* uyarısı verebilir. Bunu aşmak için ekrandaki **Ek Bilgi (More Info)** seçeneğine ve ardından beliren **Yine de Çalıştır (Run Anyway)** butonuna basabilirsiniz.

### 2. macOS Kurulumu (`AirCooler_Main-v3.7.2-macos-arm64.dmg`)
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
| `AirCooler_Main-v3.7.2-macos-arm64.dmg` | macOS (Apple Silicon) | *Build sonrası hesaplanacaktır* |
| `AirCooler_Main-v3.7.2-windows-x64.zip` | Windows (x64) | *Windows ortamında derlendiğinde hesaplanacaktır* |
