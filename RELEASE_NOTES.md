# Air Cooler Main - v3.7.0 Release Notes

Doğal gaz ve hidrokarbon karışımları için çapraz akışlı gaz soğutucu termal yük, boyutlandırma ve değerlendirme hesaplayıcısının **v3.7.0** sürümünü duyurmaktan mutluluk duyarız! Bu güncelleme ile uygulamaya güvenlik, yetkilendirme altyapısı ve gelişmiş mühendislik hesaplama yetenekleri kazandırılmıştır.

---

## 🚀 Yeni Özellikler ve İyileştirmeler

### 1. Güvenli Giriş ve Rol Yönetimi (Authentication & Authorization)
*   **Kriptografik Güvenlik:** Şifreler düz metin olarak değil, kullanıcıya özel benzersiz **rastgele tuz (salt) + SHA-256** algoritmasıyla güvenli bir şekilde hash'lenerek saklanır.
*   **Rol Tabanlı Arayüz:**
    *   **admin:** Tüm hesaplama modüllerine (`⚙️ Girişler`, `📊 Rapor`, `📐 Gelişmiş Boyutlandırma`, `📜 Kayıtlar`) tam erişim sağlar.
    *   **user:** Gelişmiş boyutlandırma sekmesini göremez, yalnızca temel sekmelere erişebilir.
*   **Çıkış Yapma (Logout):** Sidebar üzerinden oturumu kapatma desteği eklenmiştir.

### 2. Gelişmiş Çapraz Akış Sizing & Rating (Boyutlandırma & Değerlendirme)
*   **Basit Tasarım:** Cross-flow unmixed-unmixed (karışmayan-karışmayan) akış modeli için LMTD düzeltme faktörü ($F_t$) ve teorik ısı yükü hesabı.
*   **Detaylı Boyutlandırma (Sizing):** Briggs-Young dış film ısı iletim katsayısı, Kern-Kraus kanatçık verimliliği ve ESDU hava tarafı basınç düşümü modellemeleri ile gerekli yüzey alanı, fan gücü ve gaz hızı sınır kontrolü.
*   **Mevcut Durum Değerlendirme (Rating):** Geometrisi belli bir eşanjörün mevcut fan hava debisinde gaz çıkış sıcaklığı, transfer verimi ve basınç kayıpları hesabı.

### 3. macOS Derleme Desteği ve Test Güvencesi
*   PyInstaller spec dosyası çapraz platform uyumlu hale getirilmiştir.
*   Birim test kapsamı (test coverage) eklenen yeni test senaryoları ile **%91** seviyesine ulaştırılmıştır.

---

## 📦 Dağıtım Paketleri ve Kurulum Talimatları

### 1. Windows Kurulumu (`AirCooler_Main-v3.7.0-windows-x64.zip`)
1.  İndirdiğiniz `.zip` dosyasını bir klasöre çıkartın.
2.  Klasör içerisindeki `AirCooler_Main.exe` dosyasını çift tıklayarak çalıştırın.
    > [!IMPORTANT]
    > `AirCooler_Main.exe` dosyasının çalışabilmesi için klasördeki `_internal` dizininin silinmemesi ve aynı dizinde bulunması gerekmektedir.

    > [!WARNING]
    > **Windows SmartScreen Uyarısı Çıkarsa:**
    > Lisanslı dijital sertifika imzası içermeyen bağımsız projelerde Windows *"Windows kişisel bilgisayarınızı korudu"* uyarısı verebilir. Bunu aşmak için ekrandaki **Ek Bilgi (More Info)** seçeneğine ve ardından beliren **Yine de Çalıştır (Run Anyway)** butonuna basabilirsiniz.

### 2. macOS Kurulumu (`AirCooler_Main-v3.7.0-macos-arm64.dmg`)
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
| `AirCooler_Main-v3.7.0-macos-arm64.dmg` | macOS (Apple Silicon) | `a085c9fbf7164867609d1ae1a279b3370ef35fdec2944963ea5fac47acbd22ee` |
| `AirCooler_Main-v3.7.0-windows-x64.zip` | Windows (x64) | *Windows ortamında derlendiğinde hesaplanacaktır* |
