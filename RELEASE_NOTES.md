# Air Cooler Main - v4.0.0 Major Release

Doğal gaz ve hidrokarbon karışımları için çapraz akışlı gaz soğutucu termal yük, boyutlandırma ve değerlendirme hesaplayıcısının **v4.0.0** sürümünü duyurmaktan mutluluk duyarız! Bu güncelleme, kapsamlı bir kod incelemesi sonucunda **kritik fiziksel hataları gideren**, **termofiziksel doğruluğu artıran** ve **API 661 standardına uyumu sağlayan** önemli iyileştirmeler içermektedir.

---

## 🔴 Kritik Hata Düzeltmeleri

### 1. Tüp Yerleşim Geometrisi Pitch Çözücü Hatası (Fiziksel İmkansızlık Giderildi)

**Etki:** Boru eksen adımı (pitch) 63.5 mm ve 30° üçgen yerleşim seçildiğinde, `fluids` kütüphanesi pitch değerini `sin(30°)` ile çarparak enine adımı **31.75 mm** hesaplıyordu. 25.4 mm boru dış çapı + 15.9 mm kanatçık yüksekliği (= 57.2 mm toplam) ile tüpler fiziksel olarak çakışıyordu.

**Çözüm:** `resolve_pitches()` fonksiyonu eklendi. `AirCooledExchanger` artık doğrudan `pitch_normal` ve `pitch_parallel` parametreleriyle başlatılıyor, kütüphane içi `pitch_angle_solver` devre dışı bırakıldı.

**Sonuç:** Hava minimum akış alanı (`A_min`) ~24 kat artarak gerçekçi değerlere ulaştı, fan gücü 1.54 MW → ~5 kW seviyesine indi.

### 2. İki Fazlı (Yoğuşmalı) Akış Modellemesi

**Etki:** Program yoğuşma bölgesini tespit ediyor ancak boru içi ısı transfer katsayısı (`h_inside`) ve basınç düşümü (`dP_process`) için tek fazlı korelasyonlar (Dittus-Boelter / Darcy-Weisbach) kullanıyordu. Ayrıca iki faz bölgesinde ortalama sıcaklıkta `get_mixture_transport_properties` çağrısı hata veriyordu.

**Çözüm:**
- **Shah yoğuşma korelasyonu** (yatay borular, tüm rejimler) entegre edildi.
- **Lockhart-Martinelli** iki fazlı basınç düşümü modeli (türbülant-türbülant, C=20) eklendi.
- Yoğuşma tespiti: `_get_saturation_properties` ile T_in > T_çiğ ve T_out < T_kabarcık kontrolü.
- İki faz bölgesinde kalite ağırlıklı ortalama transport özellikleri hesaplanıyor.

---

## 🟡 Mühendislik İyileştirmeleri

### 3. Gnielinski Isı Transfer Korelasyonu

Dittus-Boelter (`0.023 Re^0.8 Pr^0.3`) korelasyonu, modern HTRI standartlarına uygun olarak **Gnielinski** korelasyonu ile değiştirildi:

```
Nu = (f/8)(Re-1000)Pr / [1 + 12.7(f/8)^0.5(Pr^2/3 - 1)]
```

Gnielinski, özellikle geçiş bölgesinde (2300 < Re < 4000) ve yüksek Pr sayılarında Dittus-Boelter'e göre %25'e varan doğruluk iyileştirmesi sağlar.

### 4. API 663 Fan Gücü Hesaplaması (Dinamik Basınç + Plenum Kayıpları)

Fan gücü hesabı artık yalnızca tüp demeti statik basınç kaybını değil, aşağıdaki bileşenleri de içermektedir:
- **Statik basınç kaybı** (ESDU korelasyonu) — mevcut
- **Dinamik basınç kaybı:** `ΔP_dynamic = 0.5 × ρ × v_fan²` (kullanıcı tanımlı fan çapı ve adedi ile)
- **Plenum kaybı:** Statik basıncın %10'u (API 661 yaklaşımı)
- **Toplam fan basıncı** = statik + dinamik + plenum

Yeni girişler: **Fan Çapı (m)** ve **Fan Sayısı** gelişmiş boyutlandırma sekmesinde.

---

## 🟢 API 661 Standart Uyum Denetimleri

Sizing sonuçlarında genişletilebilir **"📋 API 661 Uyum Denetimi"** paneli eklendi:

| Denetim | Kural | UI |
|---|---|---|
| Boru Dış Çapı | Min 25.4 mm (1") | ✅ Uyarı/Onay |
| Boru Duvar Kalınlığı | CS: 2.11 mm, Alaşım: 1.65 mm | ✅ Uyarı/Onay |
| Fan Kanat Uç Hızı | Mak 61 m/s (Std), 50 m/s (Düşük gürültü) | ✅ Uyarı/Onay |
| Gaz Hızı | 1-20 m/s aralığı | ✅ Mevcut (genişletildi) |

---

## 🟢 Kod Kalitesi ve Güvenlik

### 5. Ölü Kod Temizliği
`air_cooler_neqsim.py` — `assess_eos_risk` fonksiyonunda `c3plus_pct` değişkeni hesaplanıyor ancak hiçbir risk kuralında kullanılmıyordu. Temizlendi.

### 6. Varsayılan Şifre Güvenliği
Varsayılan şifrelerle (`admin123` / `user123`) giriş yapıldığında kullanıcıya **şifre değiştirme uyarısı** gösteriliyor ve değiştirme formu sunuluyor.

### 7. Soğutma Bölge Analizi (Cooling Curve)
T-H soğutma eğrisi Plotly grafiği zaten mevcut. Mavi/kırmızı/yeşil bölge renkleriyle faz geçişleri görselleştiriliyor. (v4.0.0'da değişiklik yok, sadece doğrulama.)

---

## 📦 Dağıtım Paketleri ve Kurulum Talimatları

### 1. macOS Kurulumu (`AirCooler_Main-v4.0.0-macos-arm64.dmg`)
1. İndirdiğiniz `.dmg` dosyasına çift tıklayarak mount edin.
2. `AirCooler_Main.app` dosyasını **Applications** klasörüne sürükleyin.
3. İlk çalıştırmada macOS güvenlik uyarısı alırsanız:
   - Sağ tıklayıp (Ctrl+tık) **Aç** seçeneğini kullanın, veya
   - `xattr -cr /Applications/AirCooler_Main.app` komutunu Terminal'de çalıştırın.

### 2. Windows Kurulumu (`AirCooler_Main-v4.0.0-windows-x64.zip`)
1. İndirdiğiniz `.zip` dosyasını bir klasöre çıkartın.
2. `AirCooler_Main.exe` dosyasını çift tıklayarak çalıştırın.
3. Windows SmartScreen uyarısı alırsanız: **Ek Bilgi > Yine de Çalıştır** seçeneğini kullanın.
4. `_internal` klasörü `.exe` ile aynı dizinde olmalıdır.

### Varsayılan Giriş Bilgileri
| Rol | Kullanıcı Adı | Şifre |
|---|---|---|
| Yönetici | `admin` | `admin123` |
| Standart Kullanıcı | `user` | `user123` |

> ⚠️ Varsayılan şifrelerle giriş yaptığınızda, şifre değiştirme uyarısı alacaksınız. Üretim ortamında şifrenizi değiştirmeniz önerilir.

---

## 🔒 Dosya Doğrulama (SHA-256)

| Dosya Adı | Platform | SHA-256 Değeri |
|---|---|---|
| `AirCooler_Main-v4.0.0-macos-arm64.dmg` | macOS (Apple Silicon) | `14d29af6723a9451d70fa44c89501e3f5f17baa309068c2e63b832aa13b6336c` |
| `AirCooler_Main-v4.0.0-windows-x64.zip` | Windows (x64) | *Windows ortamında derlendiğinde hesaplanacaktır* |

---

## 🔗 Bağlantılar

- **GitHub:** https://github.com/anomalyco/Air-Cooler-Main
- **AGENTS.md:** Proje mimarisi ve karar kayıtları
- **CHANGELOG.md:** Tüm sürüm geçmişi
