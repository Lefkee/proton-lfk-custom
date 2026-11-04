# Proton LFK Custom — İyileştirme ve Refactor Önerileri

> Kapsam: `proton-lfk-custom` (GE-Proton11-11 tabanlı fork). Bu doküman **kod değişikliği yapılmadan** hazırlanmış bir analiz raporudur. Tüm satır referansları bu depodaki mevcut hali işaret eder.

## 1. Yönetici Özeti

Depo büyük ölçüde upstream GE-Proton/Proton kod tabanından geliyor ve çalışır durumda; ancak fork'a özgü birkaç **kırıcı hata** ve ciddi **bakım borcu** var. En kritik üç konu:

1. **Release workflow'u geçersiz YAML** içeriyor → sürüm otomasyonu hiç çalışmıyor.
2. **Prefix upgrade yolu sessizce devre dışı** (`"GE-Proton11-11".split('-')` → 3 parça → `ValueError` yutuluyor) → eski prefix'ler hiç migrate edilmiyor.
3. **`vulkan.py` import anında `CDLL('libvulkan.so.1')` çağırıyor** → libvulkan olmayan her ortamda `proton` daha argv parse edilmeden çöküyor.

Bunlara ek olarak `utilities.py`'de iki net veri hatası (`fsr3` yanlış env değişkenine map'li, config dizini cache dizinini kullanıyor), yaygın dosya tanıtıcısı sızıntıları ve `proton` içinde 600+ satırlık iki dev fonksiyon var.

**Önerilen sıra:** P0 (kırıcı) → P1 (sessiz hatalar) → hızlı performans kazanımları → kademeli refactor. Refactor'a başlamadan önce `git submodule update --init --recursive` şart (submodule'ler şu an boş).

---

## 2. Öncelik Tablosu

| # | Öncelik | Konu | Dosya | Etki |
|---|---------|------|-------|------|
| 1 | **P0** | Geçersiz YAML | `.github/workflows/release.yml:33` | Release üretilemiyor |
| 2 | **P0** | Prefix migration ölü kod | `proton:849-851` | Eski prefix'ler upgrade edilmiyor |
| 3 | **P0** | Import'ta `libvulkan` zorunlu | `vulkan.py:26` | Ortama bağlı ani çökme |
| 4 | **P1** | `fsr3` yanlış env'e map'li | `utilities.py:63` | FSR3 ayarı FSR4'ü tetikliyor |
| 5 | **P1** | `config_dir` = cache dir | `utilities.py:32` | Kullanıcı config'i yanlış yerde |
| 6 | **P1** | Kütüphane yolu substring eşleşmesi | `proton:473-476` | Yanlış Steam kütüphanesi seçimi |
| 7 | **P1** | `copyfile_reflink` fallback kapsamı | `proton:409-423` | Sonsuz/tekrarlı başarısız deneme |
| 8 | **P1** | `HOME` KeyError | `proton:2173` | Log dizini çökmesi |
| 9 | **P1** | `sys.argv[0]` tabanlı kök dizin | `proton:2954` | PATH/symlink ile çalışmıyor |
| 10 | **P1** | fd sızıntıları | `proton:260`, `default_pfx.py:15,34` | Uzun oturumlarda fd tükenmesi |
| 11 | **P2** | Hardcoded x86_64 syscall | `proton:388-406` | Ölü kod + taşınabilirlik |
| 12 | **P2** | NVIDIA DLL taraması her açılışta | `proton:572-646` | Gecikme |
| 13 | **P2** | `xrandr` her açılışta | `proton:2243-2266` | Gecikme + stdout kirliliği |
| 14 | **P2** | `sync_appcache` her açılışta | `proton:1613-1625` | G/Ç yükü |
| 15 | **P3** | `setup_prefix` 380 satır | `proton:1233-1612` | Bakım zorluğu |
| 16 | **P3** | `init_session` 610 satır | `proton:2267-2878` | Bakım zorluğu |
| 17 | **P3** | `default_compat_config` tekrarları | `proton:1637-1877` | Bakım zorluğu |
| 18 | **P3** | `redist` hedefi idempotent değil | `Makefile.in:1864-1870` | Tekrarlanabilir build yok |
| 19 | **P3** | `configure.sh --help` exit 1 | `configure.sh` | CI/otomasyon kırılganlığı |
| 20 | **P4** | README 896 satır, tekrar | `README.md` | Doküman borcu |
| 21 | **P4** | Kırık doküman linki | `docs/DEBUGGING.md:8` | Kullanıcı deneyimi |

---

## 3. P0 — Kırıcı Sorunlar

### 3.1 Release workflow'u geçersiz YAML

**Dosya:** `.github/workflows/release.yml:33-34`

```yaml
    - name: Tags
      shell: bash
      run: |
        git fetch origin +refs/tags/*:refs/tags/*
       - name: Create Release      # ← 7 boşluk: fazla girintili
      id: create                   # ← 6 boşluk: name ile hizasız
```

`run: |` blok bittikten sonra `- name:` hem fazla girintili hem de `id:` ile uyumsuz. `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` şu hatayı veriyor:

```
ParserError: while parsing a block collection
  in "release.yml", line 30, column 7
expected <block end>, but found '<block sequence start>'
  in "release.yml", line 34, column 8
```

**Sonuç:** Workflow hiçbir zaman parse edilemiyor; release adımı çalışmıyor.

**Öneri:** Girintiyi düzelt ve repoda YAML doğrulaması ekle:

```yaml
    - name: Tags
      shell: bash
      run: |
        git fetch origin +refs/tags/*:refs/tags/*
    - name: Create Release
      id: create
      shell: bash
      run: |
        ...
```

Ek olarak `.github/workflows/` altındaki tüm dosyaları CI'da `actionlint` veya en azından `yaml.safe_load` ile doğrulayan bir `lint` job'u ekleyin.

---

### 3.2 Prefix migration sessizce atlanıyor

**Dosya:** `proton:849-851`

```python
old_proton_ver, old_prefix_ver = old_ver.split('-')
old_proton_maj, old_proton_min = old_proton_ver.split('.')
new_proton_ver, _              = CURRENT_PREFIX_VERSION.split('-')
new_proton_maj, new_proton_min = new_proton_ver.split('.')
```

`CURRENT_PREFIX_VERSION = "GE-Proton11-11"` (satır 50) ve tipik `old_ver` de `"GE-Proton10-9"` gibi. `.split('-')` **3 parça** döndürür:

```python
"GE-Proton11-11".split('-')  # ['GE', 'Proton11', '11']
```

Bu `ValueError: too many values to unpack` üretir; üstteki `except` bloğu yutarsa `upgrade_pfx()` hiçbir migration yapmadan döner. Yani prefix sürüm yükseltmeleri (registry düzeltmeleri, `tracked_files` geçişi, `old_machine_guid`) **hiç çalışmıyor**.

**Öneri:** Sürüm ayrıştırmayı tek bir yardımcıya taşı ve `CURRENT_PREFIX_VERSION`'ı türet:

```python
_PFX_VER_RE = re.compile(r'^(?:GE-)?Proton(\d+)(?:-(\d+))?$')

def parse_prefix_version(ver):
    """('GE-Proton11-11') -> (11, 11) veya None"""
    if not ver:
        return None
    m = _PFX_VER_RE.match(ver.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2) or 0)
```

`upgrade_pfx` içinde:

```python
old = parse_prefix_version(old_ver)
new = parse_prefix_version(CURRENT_PREFIX_VERSION)
if old is None or new is None:
    log(f"Prefix version parse edilemedi ({old_ver!r}); migration atlanıyor.")
    return
if new < old:
    log("Removing newer prefix")
    ...
```

Ayrıca `except` bloğunu daraltın; parse hatası **loglanmalı**, sessizce yutulmamalı.

---

### 3.3 `vulkan.py` import anında `libvulkan` yüklüyor

**Dosya:** `vulkan.py:26`

```python
libvulkan = CDLL('libvulkan.so.1')
```

`proton` → `import utilities` → `import vulkan` zinciri yüzünden **her** çalıştırma (prefix silme, `run`, `waitforexitandrun`, hatta `--help`) libvulkan'a bağımlı hale geliyor. libvulkan yoksa `OSError` import sırasında fırlar ve kullanıcı anlamsız bir traceback görür.

**Öneri:** Lazy yükleme + anlamlı hata:

```python
_libvulkan = None

def _get_libvulkan():
    global _libvulkan
    if _libvulkan is None:
        try:
            _libvulkan = CDLL('libvulkan.so.1')
        except OSError as e:
            raise VulkanError(
                "libvulkan.so.1 yüklenemedi; Vulkan sürücüsü kurulu mu?"
            ) from e
    return _libvulkan
```

Modül seviyesindeki tüm `libvulkan.xxx` kullanımlarını `_get_libvulkan().xxx` ile değiştirin (veya `Vulkan` sınıfı içinde bir kez cache'leyin).

---

## 4. P1 — Doğruluk ve Dayanıklılık

### 4.1 `fsr3` yanlış ortam değişkenine bağlı

**Dosya:** `utilities.py:62-64`

```python
'fsr3': 'PROTON_FSR4_UPGRADE',
'fsr4': 'PROTON_FSR4_UPGRADE',
```

`fsr3` anahtarı FSR4 değişkenine map'li. `user_settings.py` içinde `fsr3 = True` yazan kullanıcı farkında olmadan FSR4 upgrade'ini tetikliyor.

**Öneri:**

```python
'fsr3': 'PROTON_FSR3_UPGRADE',
'fsr4': 'PROTON_FSR4_UPGRADE',
```

`proton:2351` ve `proton:2978` zaten `PROTON_FSR3_UPGRADE` bekliyor; bu düzeltme iki tarafı tutarlı hale getirir.

---

### 4.2 `Config.Path.config_dir` cache dizinini kullanıyor

**Dosya:** `utilities.py:26-33`

```python
base_config = Path(os.getenv('XDG_CONFIG_HOME', '~/.config')).expanduser()
base_cache  = Path(os.getenv('XDG_CACHE_HOME', '~/.cache')).expanduser()

class Path(Namespace):
    config_dir: Path = base_cache.joinpath('protonfixes')   # ← yanlış
    cache_dir:  Path = base_cache.joinpath('protonfixes')
```

`base_config` tanımlanıp hiç kullanılmıyor. Kullanıcı ayarları `~/.cache` altına yazılıyor; `~/.cache` silinebilir bir dizin olduğu için ayarlar kaybolabilir.

**Öneri:**

```python
config_dir: Path = base_config.joinpath('protonfixes')
cache_dir:  Path = base_cache.joinpath('protonfixes')
```

> Not: Bu değişiklik mevcut kullanıcıların ayarlarının taşınmasını gerektirir. `config_dir` yoksa eski `cache` konumundan tek seferlik migrate eden küçük bir blok ekleyin.

---

### 4.3 Steam kütüphanesi eşleşmesi substring ile yapılıyor

**Dosya:** `proton:472-477`

```python
for path in library_paths:
    if path in g_session.env["STEAM_COMPAT_INSTALL_PATH"]:
        return get_validated_steamapps_parent(path)
```

`/games` yolu `/games2/...` ile de yanlış eşleşir; ayrıca `realpath` uygulanmadan karşılaştırma yapılıyor.

**Öneri:** Gerçek path sınırı kontrolü:

```python
install = os.path.realpath(g_session.env["STEAM_COMPAT_INSTALL_PATH"])
for path in library_paths:
    lib = os.path.realpath(path)
    try:
        if os.path.commonpath([install, lib]) == lib:
            return get_validated_steamapps_parent(path)
    except ValueError:
        continue
```

---

### 4.4 `copyfile_reflink` fallback'i eksik, döngü riski var

**Dosya:** `proton:409-423`

Mevcut davranış:
- Reflink yalnızca `ENOSYS`/`EOPNOTSUPP` durumunda global `copyfile`'a düşüyor. `EXDEV` (farklı dosya sistemi), `EINVAL` (desteklenmeyen fs), `EPERM` durumlarında **her dosya için** yeniden başarısız reflink deneniyor.
- `copy_file_range` `0` dönerse döngü ilerleme kaydetmeden dönebilir.

**Öneri:**

```python
_FALLBACK_ERRNOS = {errno.ENOSYS, errno.EOPNOTSUPP, errno.EXDEV,
                    errno.EINVAL, errno.EPERM, errno.ENOTSUP}

def copyfile_reflink(srcname, dstname):
    global copyfile
    if copyfile is not None:
        return copyfile(srcname, dstname)
    try:
        ...
        while copied < st.st_size:
            n = copy_file_range(...)
            if n == 0:
                break
            copied += n
        if copied != st.st_size:
            raise OSError(errno.EIO, "eksik kopyalama", srcname)
    except OSError as e:
        if e.errno in _FALLBACK_ERRNOS:
            copyfile = shutil.copyfile   # kalıcı fallback
            copyfile(srcname, dstname)
            return
        raise
```

---

### 4.5 `HOME` doğrudan indeksleniyor

**Dosya:** `proton:2173`

```python
basedir = self.env.get("PROTON_LOG_DIR", os.environ["HOME"])
```

`HOME` tanımsızsa (bazı container/Steam runtime senaryoları) `KeyError`. Ayrıca `self.env` yerine `os.environ` kullanımı `user_settings.py` override'larını atlıyor.

**Öneri:**

```python
basedir = self.env.get(
    "PROTON_LOG_DIR",
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~")),
)
```

`os.path.expanduser("~")` `HOME` yoksa passwd fallback'i kullanır.

---

### 4.6 Kök dizin `sys.argv[0]`'a bağlı

**Dosya:** `proton:2954`

```python
g_proton = Proton(os.path.dirname(sys.argv[0]))
```

Script PATH üzerinden veya relative symlink ile çağrıldığında `dirname` boş string veya yanlış dizin döner; `proton` kendi `dist/` kaynaklarını bulamaz.

**Öneri:**

```python
g_proton = Proton(os.path.dirname(os.path.realpath(__file__)))
```

Ayrıca `main()` başında argv doğrulaması yapın:

```python
if len(sys.argv) < 2:
    sys.stderr.write("Kullanım: proton <verb> [args]\n")
    sys.exit(2)
verb = sys.argv[1]
```

Şu an `sys.argv[1]` doğrudan indeksleniyor; argümansız çağrı `IndexError` veriyor.

---

### 4.7 Dosya tanıtıcısı sızıntıları

**Dosyalar:** `proton:260-266`, `default_pfx.py:15-22`, `default_pfx.py:33-45`

```python
sfile = open(path, "rb")
sfile.seek(0x40)
tag = sfile.read(20)
return tag.startswith(...)      # close() yok
```

Prefix taraması binlerce DLL için bu fonksiyonu çağırıyor; fd'ler GC'ye kadar açık kalıyor. `default_pfx.py` build sırasında tüm prefix'i taradığı için orada da aynı sorun var.

**Öneri:** `with open(...)` kullanın (veya `Path.read_bytes()`):

```python
def file_is_wine_builtin_dll(path):
    if not file_exists(path, follow_symlinks=True):
        return False
    try:
        with open(path, "rb") as f:
            f.seek(0x40)
            return f.read(20).startswith((b"Wine placeholder DLL", b"Wine builtin DLL"))
    except OSError:
        return False
```

`default_pfx.py`'deki `dll_bitness` için de aynısı geçerli; ayrıca `little_endian_bytes_to_uint` yerine `int.from_bytes(b, "little")` kullanılabilir.

---

### 4.8 `default_pfx.py` — shell injection / boşluklu yol hatası

**Dosya:** `default_pfx.py` (`make_default_pfx`)

Wine çağrısı string birleştirme ile `/bin/bash -c` üzerinden kuruluyor; yol boşluk veya metakarakter içeriyorsa komut bozuluyor. Aynı sorun `filter_registry` tarafında da veri bozulmasına yol açıyor (`line.strip()` + varsayılan UTF-8 decode).

**Öneri:**
- `subprocess.run([...], check=True)` ile **argüman listesi** kullanın; `shell=True`/`bash -c` kullanmayın.
- Registry dosyalarını `open(..., encoding="utf-8", errors="surrogateescape", newline="")` ile açın ve `strip()` yerine yalnızca satır sonunu (`\r\n`) kesin.
- `fixup_drive_links` içinde `os.remove` öncesi `os.path.islink` kontrolü yapın.

---

### 4.9 Diğer P1 notları

| Dosya:satır | Sorun | Öneri |
|---|---|---|
| `proton:662-711` | `get_replace_reg_value` erken `return`'lerde `.new` dosyasını bırakıyor | `with` + `try/finally`, `os.replace` atomik |
| `proton:809-832` | `remove_tracked_files` `os.remove(version_file)` korumasız | `try/except FileNotFoundError`; `destroyprefix` traceback vermesin |
| `proton:108-124` | `empty_directory` symlink dizinlerde `os.rmdir` çağırıyor (yorum "symlink handled" diyor) | `os.path.islink` kontrolü `dirs` için de doğru; `os.rmdir` yerine `shutil.rmtree` + `onerror` |
| `proton:105, 462, 1621, 1624, 1885`, `filelock.py:285` | Çıplak `except:` | `except OSError as e:` + log |
| `proton:513-570` | `type(x) != list` | `isinstance(x, list)` |
| `proton:648-660` | `os.open(dir_path, 0o644)` | `os.open(dir_path, os.O_RDONLY)` + hata yönetimi |
| `proton:130-204` | COPYPREFIX bloğu import sırasında çalışıyor, doğrulama öncesi | Fonksiyona al, `main()` içinde doğrulama sonrası çağır; `Path(None)` koruması ekle |
| `proton:1233-1612` | `setup_prefix` içinde `"msvcrt*.dll"` deseni tekrarlı | Sabit listede dedupe |

---

## 5. P2 — Performans

### 5.1 Ölü ctypes/syscall kodu

**Dosya:** `proton:385-406`

`copy_file_range_ctypes` x86_64 syscall numarası `326`'yı hardcode ediyor ve Python ≥3.8'de `os.copy_file_range` mevcut olduğu için zaten kullanılmıyor. ~25 satır ve `ctypes` bağımlılığı kaldırılabilir; ARM (FEX/Asahi) hedeflerinde de yanlış sonuç riski ortadan kalkar.

**Öneri:** Fonksiyonu ve ilgili `import ctypes` satırlarını sil; doğrudan `os.copy_file_range` kullan.

### 5.2 NVIDIA DLL taraması her açılışta

**Dosya:** `proton:572-646` — `find_nvidia_wine_dll_dir`

Her oturumda NVIDIA kütüphaneleri `dlopen` edilip DLL dizini aranıyor. Yalnızca `PROTON_ENABLE_NVAPI`/NVIDIA sürücü tespiti gerektiğinde çalıştırın; sonucu süreç içi cache'leyin.

### 5.3 `xrandr` her Wayland oturumunda

**Dosya:** `proton:2243-2266` — `get_primary_monitor`

`DISPLAY` yoksa hiç çağırmayın; `subprocess` çıktısını `stdout=subprocess.PIPE` ile susturun (şu an kullanıcının terminaline sızıyor) ve sonucu cache'leyin.

### 5.4 `sync_appcache` her açılışta

**Dosya:** `proton:1613-1625`

`dir_sync` her başlatmada çalışıyor. Appcache dizininin `mtime`'ını saklayıp değişmediyse atlayın; en azından çıplak `except`'leri loglayan hale getirin.

### 5.5 `init_session` içinde tekrarlanan env kontrolleri

**Dosya:** `proton:2267-2878`

60+ adet `check_environment(...)` çağrısı ve aynı değişkenlerin birden fazla kontrolü var:
- `PROTON_NATIVE_AGS` → `2350` ve `2359`
- FSR3/FSR4/DLSS/XESS/OPTISCALER → `init_session` içinde ve tekrar `main` içinde `2978-2984`

**Öneri:** Tek bir bildirimsel tablo:

```python
_ENV_FLAGS = [
    ("PROTON_FSR3_UPGRADE", "fsr3"),
    ("PROTON_FSR4_UPGRADE", "fsr4"),
    ("PROTON_DLSS_UPGRADE", "dlss"),
    ("PROTON_XESS_UPGRADE", "xess"),
    ("PROTON_USE_OPTISCALER", "optiscaler"),
    ("PROTON_NATIVE_AGS", None),
]

for env_key, cfg_key in _ENV_FLAGS:
    self.check_environment(env_key, cfg_key)
```

ve `user_settings` override'ları için `os.environ` yerine `self.env` kullanın.

---

## 6. P3 — Bakım / Refactor

### 6.1 `setup_prefix` (380 satır) ve `init_session` (610 satır)

**Dosya:** `proton:1233-1612`, `proton:2267-2878`

Tek fonksiyon içinde grafik DLL kopyalama, NVIDIA kütüphaneleri, Steam dosyaları, ICU, OpenVR, registry vb. iç içe geçmiş. Öneri:

```
setup_prefix()
├── _setup_graphics_dlls()      # dxvk/vkd3d/d7vk kopyaları
├── _setup_nvidia_libs()
├── _setup_steam_files()
├── _setup_icu()                # aşağıya bakın
└── _setup_openvr()
```

Her yardımcı tek sorumluluk taşımalı ve `prefix_dir` parametresi almalı. Bu, test edilebilirliği de artırır.

### 6.2 ICU sürümü koda gömülü

**Dosya:** `proton` (`setup_prefix` içinde `icuin68`, `icuuc68`, `icudt68`)

Wine'ın ICU sürümü yükseldiğinde `proton` elle güncellenmeli; aksi halde sessiz DLL eksikliği. Build sırasında (`configure.sh`/Makefile) ICU major sürümünü tespit edip bir üretilmiş sabit (`_icu_version`) olarak yazın veya dizini glob ile bulun:

```python
icu_dlls = sorted(prefix_lib.glob("icu*[0-9]*.dll"))
```

### 6.3 `default_compat_config` tekrarı

**Dosya:** `proton:1637-1877`

~240 satır, aynı appid listelerinin config anahtarlarına tekrar tekrar yazılması. Tersine çevrilmiş bir map ile üretin:

```python
_COMPAT_APPIDS = {
    "PROTON_NO_ESYNC": {"883710", " ... "},
    "PROTON_ENABLE_NVAPI": {" ... "},
}

def default_compat_config():
    cfg = {}
    for key, appids in _COMPAT_APPIDS.items():
        for appid in appids:
            cfg.setdefault(appid, set()).add(key)
    return cfg
```

Yinelenen bloklar (`SteamGameId == "1183470"` → `WINE_MONO_HIDETYPES`, `proton:2647` ve `2739`) tek yerde toplanmalı.

### 6.4 `filelock.py` — 451 satırlık vendored kütüphane

**Dosya:** `filelock.py`

Sürüm 3.0.12; Linux'ta Windows/Soft kilitleme sınıfları ölü kod. `time.time()` yerine `time.monotonic()` kullanılmalı, çıplak `except:` var.

**Öneri:** İki seçenek:
1. `requirements.txt`/sistem bağımlılığı olarak güncel `filelock` paketini kullan.
2. Linux'a özel ~40 satırlık `fcntl.flock` sarmalayıcısı yaz:

```python
import fcntl, os

class FileLock:
    def __init__(self, path):
        self._f = open(path, "a+")
    def __enter__(self):
        fcntl.flock(self._f, fcntl.LOCK_EX)
        return self
    def __exit__(self, *exc):
        fcntl.flock(self._f, fcntl.LOCK_UN)
        self._f.close()
```

### 6.5 `steampipe_fixups.py` global durum

**Dosya:** `steampipe_fixups.py`

- `empty_dirs` / `no_write_paths` modül seviyesinde ve sıfırlanmıyor → aynı süreçte ikinci çağrı yanlış sonuç verir.
- `do_restore` içinde `os.lstat` eksik dosyada exception fırlatıyor.
- `write_manifest` dosyayı kapatmıyor.
- `canonicalize` `str.replace` kullanıyor; `os.path.relpath` daha doğru.

**Öneri:** Durumu sınıfa taşı (`class FixupState`), tüm dosya işlemlerini `with` ile yap, `FileNotFoundError`'ı yakala.

### 6.6 `remove_tracked_files` / `destroyprefix`

**Dosya:** `proton:809-832`

`version_file` yoksa `os.remove` traceback veriyor. Kullanıcıya "prefix silindi" mesajı yerine Python stack trace gösteriyor. `try/except FileNotFoundError` + `log()` ile düzeltin.

---

## 7. Build ve CI

### 7.1 `redist` hedefi idempotent değil

**Dosya:** `Makefile.in:1864-1870`

```make
redist: all
	mkdir -p $(REDIST_DIR)
	rsync --delete -arx $(DST_BASE)/ $(REDIST_DIR)
	mv $(REDIST_DIR) $(BUILD_NAME)          # ikinci çalıştırmada iç içe geçer
	tar -cvzf $(BUILD_NAME).tar.gz $(BUILD_NAME)
```

İkinci `make redist` çağrısında `mv` hedefi zaten var olduğu için `$(BUILD_NAME)/$(REDIST_DIR)` oluşur veya hata verir. Ayrıca `tar -cvzf` `SOURCE_DATE_EPOCH`'a rağmen tekrarlanabilir değil (mtime/owner/sıra).

**Öneri:**

```make
redist: all
	rm -rf $(BUILD_NAME) $(BUILD_NAME).tar.gz
	mkdir -p $(BUILD_NAME)
	rsync -a --delete $(DST_BASE)/ $(BUILD_NAME)/
	tar --sort=name --mtime=@$(SOURCE_DATE_EPOCH) \
	    --owner=0 --group=0 --numeric-owner \
	    -C $(dir $(BUILD_NAME)) -cf - $(notdir $(BUILD_NAME)) | gzip -9n > $(BUILD_NAME).tar.gz
	sha256sum $(BUILD_NAME).tar.gz > $(BUILD_NAME).sha256sum
```

### 7.2 `all-dist` sürüm tespiti kırılgan

**Dosya:** `Makefile.in:1840-1842`

`git describe` fallback'siz; source tarball veya shallow clone'da build kırılır. `VERSION` dosyası zaten var:

```make
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || cat VERSION)
```

### 7.3 `configure.sh`

- `--help`/`--usage` → `usage info` çağırıyor ve **exit 1** ile çıkıyor; yardım isteyen otomasyon başarısız sayıyor. `exit 0` olmalı.
- `escape_for_make` `%` ve satır sonlarını escape etmiyor.
- `DOCKER_OPTS` / `CONTAINER_MOUNT_OPTS` yazılırken escape edilmiyor → boşluk/metakarakter içeren mount yolları bozuluyor.

### 7.4 `_job_build.yml`

- `./patches/protonprep-valve-staging.sh || true` → patch uygulama hataları sessizce yutuluyor. En azından `|| { echo "patch failed"; exit 1; }` veya bilinçli istisnalar için açık allowlist kullanın.
- ccache anahtarı `ccache-proton-${{ github.run_id }}` her run'da değişiyor → restore her zaman miss. `hashFiles('patches/**', 'Makefile.in', 'configure.sh')` tabanlı içerik anahtarı kullanın.

### 7.5 Submodule'ler başlatılmamış

`git submodule status` tüm girdilerde `-` gösteriyor; `protonfixes/` boş. Build/çalıştırma öncesi:

```bash
git submodule update --init --recursive
```

CI'da `actions/checkout` adımına `submodules: recursive` ekleyin (mevcut workflow'larda kontrol edilmeli).

---

## 8. Dokümantasyon

### 8.1 README 896 satır

- Native ve Flatpak kurulum scriptleri neredeyse birebir tekrar ediyor (~126-238 ve ~284-396). Ortak script `scripts/install-common.sh` olarak çıkarılmalı, README sadece link vermeli.
- "Tested games" ve uzun seçenek listeleri `docs/` altına taşınmalı; README bir "hızlı başlangıç" olarak ~200 satıra inmeli.

### 8.2 Kırık link

**Dosya:** `docs/DEBUGGING.md:8`

```markdown
See [README.md#debugging](../README.md#debugging).
```

README'de `## Debugging` bölümü/anchor'ı yok. Ya README'ye bölüm ekleyin ya da linki `docs/DEBUGGING.md` içindeki ilgili başlığa çevirin.

### 8.3 Eksik doküman

- `VERSION` ile `proton:50` `CURRENT_PREFIX_VERSION` ilişkisi dokümante edilmeli (bkz. 3.2).
- Fork'a özgü değişikliklerin listesi (`docs/FORK_NOTES.md`) yok; upstream rebase sırasında çakışma çözümü zorlaşıyor (`docs/REBASING_TIPS.md` var ama fork farkları listelenmemiş).

---

## 9. Güvenlik — `umu_helper/umu.c`

| Satır | Sorun | Öneri |
|---|---|---|
| `263`, `268` | `sprintf` → `char path[MAX_PATH]` taşması (`ff.cFileName` uzunluğuna bağlı) | `snprintf(path, sizeof(path), ...)` + dönüş kontrolü |
| `100`, `111` | `malloc`/`realloc` sonucu kontrol edilmiyor | `if (!ptr) { ... }` |
| `346`, `358`, `379` | `malloc` sonuçları kontrolsüz | Aynı |
| `wine_get_dos_file_name` | `NULL` dönüş kontrolü yok | Erken çıkış + hata mesajı |

Örnek:

```c
int n = snprintf(path, sizeof(path),
                 "C:\\Program Files\\Electronic Arts\\EA Desktop\\%s\\EA Desktop\\Link2EA.exe",
                 ff.cFileName);
if (n < 0 || (size_t)n >= sizeof(path)) {
    fprintf(stderr, "umu: yol çok uzun, atlanıyor\n");
    continue;
}
```

---

## 10. Hızlı Kazanımlar (tek oturumda yapılabilir)

1. `release.yml` girintisini düzelt + `actionlint` job'u ekle.
2. `utilities.py:63` → `PROTON_FSR3_UPGRADE`.
3. `utilities.py:32` → `base_config`.
4. `vulkan.py` lazy yükleme.
5. `proton:2954` → `realpath(__file__)`; `main()` argv kontrolü.
6. `proton:2173` → `os.environ.get`.
7. `proton:473` → `commonpath`.
8. Tüm `open()` çağrılarını `with`'e çevir (`proton`, `default_pfx.py`, `steampipe_fixups.py`).
9. `docs/DEBUGGING.md:8` linkini düzelt.
10. `Makefile.in` `redist` hedefini idempotent yap.

Bunlar davranış değişikliği riski düşük, faydası yüksek değişiklikler.

---

## 11. Önerilen Yol Haritası

| Aşama | İçerik | Risk |
|---|---|---|
| 1 | P0 düzeltmeleri (YAML, prefix versiyon parse, vulkan lazy) | Düşük |
| 2 | Hızlı kazanımlar (bölüm 10) | Düşük |
| 3 | fd sızıntıları, `default_pfx.py` argüman listesi, `umu.c` snprintf | Orta |
| 4 | Performans kapıları (NVIDIA, xrandr, appcache, env tablosu) | Orta |
| 5 | `setup_prefix` / `init_session` bölme, `default_compat_config` tablosu | Yüksek (davranış testi gerekir) |
| 6 | `filelock.py` değişimi, `redist` tekrarlanabilirlik, doküman | Düşük |

Her aşama sonunda en azından şu duman testleri çalıştırılmalı:

```bash
./proton --help                      # argv/help yolu
./proton run <küçük test exe>        # temel çalıştırma
./proton waitforexitandrun <exe>     # Steam benzeri yol
./configure.sh --help; echo $?       # 0 dönmeli
make -n redist                       # komut üretimi
python3 -m py_compile proton utilities.py default_pfx.py steampipe_fixups.py vulkan.py
```

---

## 12. Dokunulmaması Gerekenler

- **`lsteamclient/`, `vrclient_x64/`**: `unixlib_generated.h` dosyaları (2.9 MB / 1.8 MB) üretilmiş kod; elle düzenleme upstream ile çakışır. Değişiklik gerekiyorsa ilgili `.idl`/üretici script kullanılmalı.
- **`fonts/`**: 27 MB'lık ikili dosyalar; Git LFS veya build-time indirme değerlendirilebilir, ancak mevcut yapı bozulmamalı.
- **Submodule içerikleri** (`wine/`, `dxvk/`, `vkd3d-proton/` vb.): fork değişiklikleri `patches/` üzerinden yapılmalı; submodule commit'lerini doğrudan değiştirmek rebase'i zorlaştırır.

---

## 13. Referans Özeti

| Dosya | Kritik satırlar |
|---|---|
| `proton` | 50, 105, 108-124, 130-204, 260-266, 385-423, 455-478, 513-570, 572-660, 662-711, 809-851, 1015-1027, 1233-1612, 1613-1625, 1637-1877, 2173, 2243-2266, 2267-2878, 2350-2359, 2647, 2739, 2954, 2978-2984 |
| `utilities.py` | 26-33, 62-64 |
| `vulkan.py` | 26 |
| `default_pfx.py` | 15-22, 33-45, `make_default_pfx`, `filter_registry`, `fixup_drive_links` |
| `steampipe_fixups.py` | modül global'leri, `do_restore`, `write_manifest`, `canonicalize` |
| `filelock.py` | 285 (bare except), `time.time()` kullanımları |
| `Makefile.in` | 1840-1842, 1864-1870 |
| `configure.sh` | `usage`, `escape_for_make`, `DOCKER_OPTS` |
| `.github/workflows/release.yml` | 33-34 |
| `.github/workflows/_job_build.yml` | patch `|| true`, ccache anahtarı |
| `docs/DEBUGGING.md` | 8 |
| `umu_helper/umu.c` | 100, 111, 263, 268, 346, 358, 379 |
