/**
 * Form Builder - Real-Time Validation & Formatting System v1.2
 * Türkiye'ye özel validasyonlar + Input maskeleme/formatlama
 * Düzenlendi: ES6+, Class Yapısı, BigInt Desteği
 */
/**
 * Form Builder - Real-Time Validation & Formatting System v1.3
 * Türkiye'ye özel validasyonlar + Input maskeleme + Gelişmiş Kontroller
 * (Date Range, Age Calc, Password Match eklendi)
 */

// ==========================================
// 0. GLOBAL AYARLAR
// ==========================================
window.DXDropzoneDefaults = { maxMb: 10, totalMaxMb: 0, strictMode: false, batchReject: false };


// Çeviri Yardımcısı
function t(key, defaultText) {
    if (window.FormBuilderI18n && window.FormBuilderI18n[key]) {
        return window.FormBuilderI18n[key];
    }
    return defaultText || key;
}

(function () {
    'use strict';

    console.log('🚀 Form Builder Validation & Formatting System v1.2 yükleniyor...');

    // ==========================================
    // TÜRKÇE HATA MESAJLARI
    // ==========================================
    // ==========================================
    // 1. MESSAGES (Hata Mesajları)
    // ==========================================
    const MESSAGES = { 
        required: t('required', 'Bu alan zorunludur'),
        minLength: t('min_length', 'En az {min} karakter girilmelidir'),
        maxLength: t('max_length', 'En fazla {max} karakter girilebilir'),
        min: t('min_val', 'Değer en az {min} olmalıdır'),
        max: t('max_val', 'Değer en fazla {max} olabilir'),
        email: t('email_error', 'Geçerli bir e-posta adresi giriniz'),
        url: t('url_error', 'Geçerli bir URL giriniz'),
        phoneTR: t('phone_error', 'Geçerli bir telefon numarası giriniz (5xx...)'),
        tckn: t('tckn_error', 'Geçersiz TC Kimlik Numarası'),
        vkn: t('vkn_error', 'Geçersiz Vergi Kimlik Numarası'),
        iban: t('iban_error', 'Geçerli bir IBAN giriniz'),
        plate: t('plate_error', 'Geçerli bir araç plakası giriniz (Örn: 34 ABC 123)'),
        creditCard: t('cc_error', 'Geçerli bir kredi kartı numarası giriniz'),
        date: t('date_error', 'Geçerli bir tarih giriniz (GG.AA.YYYY)'),
        dateRange: t('date_range_error', 'Başlangıç tarihi bitişten büyük olamaz'),
        match: t('match_error', 'Değerler eşleşmiyor'),
        number: t('number_error', 'Geçerli bir sayı giriniz'),
        otp: t('otp_error', '{length} haneli kodu giriniz'),
    
        phoneTRLength: 'Telefon numarası 10 haneli olmalıdır ({current}/10)',
        phoneTRPrefix: 'Cep telefonu 5 ile başlamalıdır',    
        tcknLength: 'TC Kimlik No 11 haneli olmalıdır ({current}/11)',
        tcknFirstZero: 'TC Kimlik No 0 ile başlayamaz',
        tcknAlgorithm: 'TC Kimlik Numarası doğrulanamadı',
        vknLength: 'Vergi No 10 haneli olmalıdır ({current}/10)',
        vknAlgorithm: 'Vergi Kimlik Numarası doğrulanamadı',
        ibanLength: 'IBAN 26 karakter olmalıdır ({current}/26)',
        ibanPrefix: 'IBAN "TR" ile başlamalıdır',
        ibanAlgorithm: 'IBAN doğrulanamadı',
        plateCity: 'İl kodu 01-81 arasında olmalıdır',
        creditCardLength: 'Kredi kartı numarası eksik ({current}/16)',
        creditCardAlgorithm: 'Kredi kartı numarası geçersiz',
        dateFuture: 'Gelecek tarih seçilemez',
        dateInvalid: 'Geçersiz tarih',
        pattern: 'Geçersiz format',
        invalid: 'Geçersiz değer'
    };

    const formatMessage = (template, params) => {
        if (!params) return template;
        return Object.keys(params).reduce((msg, key) => {
            return msg.replace(new RegExp(`\\{${key}\\}`, 'g'), params[key]);
        }, template);
    };

    // ==========================================
    // 2. WIDGETLAR (Eksik Olanlar Geri Geldi)
    // ==========================================

    // 2.1 Dosya Yükleme (Dropzone)
    function initFileDropzones() {
        $('.file-dropzone').each(function() {
            var $zone = $(this);
            if ($zone.data('dzInit')) return;
            $zone.data('dzInit', true);
            
            var inputId = $zone.data('input');
            var $input = $('#' + inputId);
            var $list = $zone.parent().find('.file-list');
            if (!$list.length) $list = $('<ul class="list-unstyled file-list mt-3"></ul>').appendTo($zone.parent());
            
            var maxMb = parseFloat($zone.data('max-size') || 10);
            var state = { files: [] };

            function renderFiles() {
                $list.empty();
                state.files.forEach(function(f, idx) {
                    var sizeMB = (f.size / 1024 / 1024).toFixed(2);
                    var li = $('<li class="d-flex justify-content-between align-items-center py-2 border-bottom"></li>');
                    var info = $('<div><i class="fas fa-file me-2"></i><span class="fw-bold">' + f.name + '</span> <small class="text-muted">(' + sizeMB + ' MB)</small></div>');
                    var btn = $('<button type="button" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></button>');
                    if (f.size / 1024 / 1024 > maxMb) info.append(' <span class="badge bg-danger">' + t('too_big', 'Çok Büyük') + '</span>');
                    btn.on('click', function() { state.files.splice(idx, 1); syncInput(); renderFiles(); });
                    li.append(info).append(btn);
                    $list.append(li);
                });
            }
            function syncInput() {
                var dt = new DataTransfer();
                state.files.forEach(function(f) { dt.items.add(f); });
                $input[0].files = dt.files;
                $input.trigger('change');
            }
            $zone.on('dragover', function(e) { e.preventDefault(); $zone.addClass('border-primary bg-light'); });
            $zone.on('dragleave', function(e) { e.preventDefault(); $zone.removeClass('border-primary bg-light'); });
            $zone.on('drop', function(e) {
                e.preventDefault(); $zone.removeClass('border-primary bg-light');
                if (e.originalEvent.dataTransfer.files.length) {
                    Array.from(e.originalEvent.dataTransfer.files).forEach(f => state.files.push(f));
                    syncInput(); renderFiles();
                }
            });
            $zone.find('button').on('click', function() { $input.click(); });
            $input.on('change', function() {
                if (this.files.length) { Array.from(this.files).forEach(f => state.files.push(f)); renderFiles(); }
            });
        });
    }

    // 2.2 Harita (Leaflet)
    function initMapPoint() {
        if (typeof L === 'undefined') return;
        $('.dx-map-point').each(function() {
            var $el = $(this); if ($el.data('mapInit')) return; $el.data('mapInit', true);
            var name = $el.data('name');
            var lat = parseFloat($el.data('lat') || 39.925), lng = parseFloat($el.data('lng') || 32.836);
            var map = L.map($el.attr('id')).setView([lat, lng], parseInt($el.data('zoom') || 10));
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
            var marker = L.marker([lat, lng], { draggable: true }).addTo(map);
            function update(pos) {
                $('#' + name + '_lat').val(pos.lat.toFixed(6));
                $('#' + name + '_lng').val(pos.lng.toFixed(6)).trigger('change');
                $('#' + name + '_coord').text(pos.lat.toFixed(6) + ', ' + pos.lng.toFixed(6));
            }
            marker.on('dragend', function(e) { update(e.target.getLatLng()); });
            map.on('click', function(e) { marker.setLatLng(e.latlng); update(e.latlng); });
            setTimeout(() => map.invalidateSize(), 500);
        });
    }

    // 2.3 İmza
    // 2.3 İmza (Gelişmiş Resize Destekli)
    function initSignaturePad() {
        if (typeof SignaturePad === 'undefined') return;
        
        $('.dx-signature-pad').each(function() {
            var $wrap = $(this);
            var canvas = $wrap.find('canvas')[0];
            var $input = $('#' + $wrap.data('input'));
            
            // Canvas boyutlandırma fonksiyonu (Retina ekranlar için kritik)
            function resizeCanvas() {
                var ratio = Math.max(window.devicePixelRatio || 1, 1);
                canvas.width = canvas.offsetWidth * ratio;
                canvas.height = canvas.offsetHeight * ratio;
                canvas.getContext("2d").scale(ratio, ratio);
            }
            
            // İlk boyutlandırma
            resizeCanvas();
            
            // SignaturePad başlat
            var signaturePad = new SignaturePad(canvas, { 
                backgroundColor: 'rgb(255, 255, 255)',
                penColor: '#000000'
            });
            
            // Mevcut veri varsa yükle
            if ($input.val()) {
                signaturePad.fromDataURL($input.val(), { ratio: 1 }); // ratio: 1 önemli
            }
            
            // Çizim bittiğinde inputa yaz
            signaturePad.addEventListener("endStroke", () => { 
                if (!signaturePad.isEmpty()) {
                    $input.val(signaturePad.toDataURL()).trigger('input').trigger('change');
                }
            });
            
            // Temizle Butonu
            $wrap.find('[data-action="sig-clear"]').on('click', () => { 
                signaturePad.clear(); 
                $input.val('').trigger('input').trigger('change'); 
            });
            
            // Pencere boyutu değişirse canvas'ı güncelle
            window.addEventListener("resize", function() {
                resizeCanvas();
                // Not: Resize canvas'ı temizler, veriyi geri yüklemek gerekebilir.
                // Basitlik adına burada bırakıyoruz, gelişmiş versiyonda data saklanmalı.
            });
        });
    }

    // 2.4 Rich Text
    function initRichText() {
        if (typeof Quill === 'undefined') return;
        $('[id$="_editor"]').each(function() {
            var $editor = $(this); var inputId = $editor.data('target');
            var quill = new Quill('#' + $editor.attr('id'), { theme: 'snow', placeholder: $editor.data('placeholder') });
            quill.on('text-change', function() {
                var html = quill.root.innerHTML;
                $('#' + inputId).val(html === '<p><br></p>' ? '' : html).trigger('change');
            });
        });
    }

    // 2.5 Barkod
    // 2.5 Barkod (Gelişmiş - form-builder.js'den Port Edildi)
    // 2.5 Barkod (Düzeltilmiş - Dosyadan Okuma Hatası Giderildi)
    function initBarcode() {
        if (typeof Html5Qrcode === 'undefined') {
            console.warn('Html5Qrcode kütüphanesi yüklü değil.');
            return;
        }
        
        var scanners = {}; // Aktif tarayıcıları tutar

        // 1. Kamerayı Başlat
        $(document).off('click.startScan').on('click.startScan', '[data-action="start-scan"]', function() {
            var $btn = $(this);
            var readerId = $btn.data('reader');
            var inputName = $btn.data('input');
            var $stopBtn = $btn.siblings('[data-action="stop-scan"]');
            var $resultDiv = $('#barcode_result_' + inputName);
            var $hiddenInput = $('#' + inputName);

            if (scanners[readerId]) return; 

            var html5QrCode = new Html5Qrcode(readerId);
            scanners[readerId] = html5QrCode;

            $('#' + readerId).show();
            
            html5QrCode.start(
                { facingMode: "environment" }, 
                { fps: 10, qrbox: { width: 250, height: 250 } },
                function(decodedText, decodedResult) {
                    $hiddenInput.val(decodedText).trigger('input').trigger('change');
                    var formatName = decodedResult.result.format ? decodedResult.result.format.formatName : 'Format';
                    
                    $resultDiv.removeClass('alert-info alert-danger').addClass('alert-success');
                    $resultDiv.html('<i class="fas fa-check-circle me-2"></i><strong>Okundu:</strong> ' + formatName + '<br><code class="fs-6">' + decodedText + '</code>');
                    
                    html5QrCode.stop().then(function() {
                        delete scanners[readerId];
                        $btn.show(); $stopBtn.hide(); $('#' + readerId).hide();
                    });
                },
                function(errorMessage) {}
            ).then(function() {
                $btn.hide(); $stopBtn.show();
                $resultDiv.removeClass('alert-success alert-danger').addClass('alert-info');
                $resultDiv.html('<i class="fas fa-camera me-2"></i>Kamera aktif.');
            }).catch(function(err) {
                $resultDiv.removeClass('alert-info alert-success').addClass('alert-danger');
                $resultDiv.html('<i class="fas fa-exclamation-triangle me-2"></i>Kamera hatası: ' + err);
                delete scanners[readerId];
            });
        });

        // 2. Kamerayı Durdur
        $(document).off('click.stopScan').on('click.stopScan', '[data-action="stop-scan"]', function() {
            var $btn = $(this);
            var readerId = $btn.data('reader');
            var $startBtn = $btn.siblings('[data-action="start-scan"]');
            var inputName = $btn.data('input');
            var $resultDiv = $('#barcode_result_' + inputName);

            if (scanners[readerId]) {
                scanners[readerId].stop().then(function() {
                    delete scanners[readerId];
                    $btn.hide(); $startBtn.show(); $('#' + readerId).hide();
                    $resultDiv.html('<i class="fas fa-info-circle me-2"></i>Kamera durduruldu.');
                });
            }
        });

        // 3. Dosyadan Barkod Okuma (DÜZELTİLEN KISIM)
        $(document).off('change.fileScan').on('change.fileScan', 'input[type="file"][id^="barcode_file_"]', function() {
            var $fileInput = $(this);
            var inputName = $fileInput.data('input');
            var file = this.files[0];
            if (!file) return;

            var $hiddenInput = $('#' + inputName);
            var $resultDiv = $('#barcode_result_' + inputName);

            $resultDiv.removeClass('alert-success alert-danger').addClass('alert-info');
            $resultDiv.html('<div class="spinner-border spinner-border-sm me-2"></div>Resim işleniyor...');

            // --- DÜZELTME BAŞLANGIÇ ---
            // 1. Benzersiz bir ID oluştur
            var tempDivId = "temp-barcode-reader-" + Date.now();
            
            // 2. Bu ID ile DOM'a görünmez bir DIV ekle (Kütüphane bunu arayacak)
            $('body').append('<div id="' + tempDivId + '" style="display:none;"></div>');

            // 3. Kütüphaneyi bu ID ile başlat
            var html5QrCode;
            try {
                html5QrCode = new Html5Qrcode(tempDivId);
            } catch (e) {
                console.error("Html5Qrcode başlatılamadı:", e);
                $('#' + tempDivId).remove(); // Hata olursa temizle
                return;
            }
            // --- DÜZELTME BİTİŞ ---
            
            html5QrCode.scanFile(file, true)
                .then(function(decodedText) {
                    $hiddenInput.val(decodedText).trigger('input').trigger('change');
                    $resultDiv.removeClass('alert-info alert-danger').addClass('alert-success');
                    $resultDiv.html('<i class="fas fa-check-circle me-2"></i><strong>Dosyadan Okundu:</strong><br><code class="fs-6">' + decodedText + '</code>');
                })
                .catch(function(err) {
                    $resultDiv.removeClass('alert-info alert-success').addClass('alert-danger');
                    $resultDiv.html('<i class="fas fa-exclamation-triangle me-2"></i>Barkod bulunamadı.');
                    console.error(err);
                })
                .finally(function() {
                    // 4. İşlem bitince geçici DIV'i sil (Temizlik)
                    html5QrCode.clear();
                    $('#' + tempDivId).remove();
                    $fileInput.val(''); // Input'u temizle ki aynı dosyayı tekrar seçebilsin
                });
        });

        // 4. Temizle Butonu
        $(document).off('click.clearBarcode').on('click.clearBarcode', '[data-action="clear-barcode"]', function() {
            var inputName = $(this).data('input');
            $('#' + inputName).val('').trigger('input');
            $('#barcode_file_' + inputName).val('');
            $('#barcode_result_' + inputName).removeClass('alert-success alert-danger').addClass('alert-info')
                .html('<i class="fas fa-info-circle me-2"></i>Henüz kod okunmadı.');
        });
    }

    // 2.6 Hesaplama   buraya gel
    // 2.6 Otomatik Hesaplama (GÜÇLENDİRİLMİŞ VERSİYON)
    function initAutoCalculation() {
        $('[data-calc-formula]').each(function() {
            var $target = $(this); 
            var formula = $target.data('calc-formula'); // Örn: "{miktar} * {fiyat}"
            
            // Formüldeki değişkenleri bul (Örn: ['{miktar}', '{fiyat}'])
            var variables = formula.match(/\{[\w\-_]+\}/g) || [];
            
            function calculate() {
                var calcString = formula;
                var allValid = true;

                variables.forEach(function(v) {
                    var id = v.replace(/[\{\}]/g, ''); // {miktar} -> miktar
                    var $input = $('#' + id);
                    var rawVal = $input.val();

                    // TR Para Birimi Temizliği (1.250,50 -> 1250.50)
                    // Noktaları sil, virgülü nokta yap
                    var val = 0;
                    if(rawVal) {
                        var cleanVal = rawVal.toString().replace(/\./g, '').replace(',', '.');
                        val = parseFloat(cleanVal);
                    }

                    if (isNaN(val)) {
                        val = 0;
                        // Eğer formüldeki değişkenlerden biri sayı değilse hesaplamayı durdurabiliriz
                        // allValid = false; 
                    }
                    
                    calcString = calcString.replace(v, val);
                });

                try {
                    // Hesapla
                    var result = new Function('return ' + calcString)();
                    
                    // Sonsuz (Infinity) veya NaN kontrolü (Sıfıra bölme vb.)
                    if (!isFinite(result) || isNaN(result)) {
                        result = 0;
                    }

                    // Sonucu TR formatına çevir (1.250,50)
                    var formatted = result.toLocaleString('tr-TR', { 
                        minimumFractionDigits: 2, 
                        maximumFractionDigits: 2 
                    });
                    
                    // Hedefe yaz
                    if ($target.is('input')) {
                        $target.val(formatted);
                        // Eğer hedef de başka bir formülün parçasıysa tetikle
                        $target.trigger('change'); 
                    } else {
                        $target.text(formatted);
                    }
                    
                } catch(e) {
                    console.error("Hesaplama Hatası:", e);
                }
            }
            
            // Değişkenleri dinle
            variables.forEach(function(v) { 
                var inputId = v.replace(/[\{\}]/g, '');
                // 'input' ve 'change' olaylarını dinle
                $('#' + inputId).on('input change keyup', calculate); 
            });
            
            // İlk açılışta hesapla
            calculate();
        });
    }

    // 2.7 Koşullu Mantık
    // 2.7 Koşullu Mantık (GÜNCELLENMİŞ - RADIO BUTTON DESTEKLİ)
    function initConditionalLogic() {
        $('[data-conditional-field]').each(function() {
            var $field = $(this); // Gizlenip/Açılacak alan (Wrapper)
            var parentName = $field.data('conditional-field'); // Tetikleyen alanın adı (örn: tur)
            var targetVal = $field.data('conditional-value'); // Beklenen değer (örn: CEK)
            
            // Tetikleyen input grubunu bul
            var $parent = $('[name="' + parentName + '"], [name="' + parentName + '[]"]');
            
            // Alanı kapsayan container'ı bul (Kart, satır veya sütun olabilir)
            var $container = $field.closest('.mb-3, .col-12, .col-md-6, .card');
            
            // Eğer $field zaten bir container ise (örn: master-detail container), kendisine uygula
            if ($field.hasClass('master-detail-container') || $field.hasClass('card')) {
                $container = $field;
            }

            function check() {
                var val;

                // 1. Radio Button Kontrolü (ÖZEL DURUM)
                if ($parent.is(':radio')) {
                    // Sadece SEÇİLİ olanın değerini al
                    val = $('input[name="' + parentName + '"]:checked').val();
                } 
                // 2. Checkbox Kontrolü
                else if ($parent.is(':checkbox')) {
                    val = $parent.is(':checked') ? 'true' : 'false';
                } 
                // 3. Standart Input/Select Kontrolü
                else {
                    val = $parent.val();
                }

                // Karşılaştırma (String'e çevirerek yapıyoruz ki tür hatası olmasın)
                var isVisible = false;
                
                if (targetVal === undefined || targetVal === null) {
                    isVisible = !!val; // Değer varsa göster
                } else if (Array.isArray(targetVal)) {
                    isVisible = targetVal.includes(val); // Liste içindeyse göster
                } else {
                    isVisible = (String(val) === String(targetVal)); // Eşitse göster
                }

                // Animasyonlu Göster/Gizle
                if (isVisible) {
                    $container.removeClass('d-none').fadeIn(200);
                    // İçindeki inputların disable durumunu kaldır (Veri gönderilebilsin)
                    $container.find('input, select, textarea').prop('disabled', false);
                } else {
                    $container.hide(); // d-none yerine hide kullandık, fadeOut karışabilir
                    // Gizlenen alanları disable et (Validation hatası vermesin ve post edilmesin)
                    $container.find('input, select, textarea').prop('disabled', true);
                }
            }

            // Olay Dinleyicileri
            $parent.on('change input click', check); // click event'i radio için bazen gerekebilir
            
            // Başlangıç kontrolü
            check();
        });
    }

    // 2.8 Akıllı Bağımlı Seçim (Geliştirilmiş Select2 Uyumlu Motor)
    function initDependentSelects() {
        $('select[data-dependent-parent]').each(function() {
            var $child = $(this); 
            var parentName = $child.data('dependent-parent');
            var url = $child.data('source-url');
            // ✨ YENİ: Özel parametre adı belirlendiyse onu kullan, yoksa parent_id kullan
            var paramName = $child.data('source-param') || 'parent_id';
            
            // Parent'ı ID veya Name ile güvenli şekilde bul
            var $parent = $('#' + parentName + ', [name="' + parentName + '"]').first();
            
            if ($parent.length === 0) return;

            $parent.on('change', function() {
                var pid = $(this).val();
                
                // Parent boşaltıldıysa (Örn: Temizle'ye basıldıysa)
                if (!pid) { 
                    $child.empty().append('<option value="">' + t('select', 'Seçiniz...') + '</option>').prop('disabled', true);
                    // Select2'yi yenile ve altındakileri de temizlemek için zincirleme tetikle
                    $child.trigger('change'); 
                    if ($child.hasClass('select2-hidden-accessible')) $child.trigger('change.select2');
                    return; 
                }
                
                var originalPlaceholder = $child.find('option:first').text() || t('select', 'Seçiniz...');
                
                // Yükleniyor durumu ve Select2 arayüz güncellemesi
                $child.prop('disabled', true).empty().append('<option value="">' + t('loading', 'Yükleniyor...') + '</option>');
                if ($child.hasClass('select2-hidden-accessible')) $child.trigger('change.select2');

                // İstek parametresini dinamik hazırla
                var requestData = {};
                requestData[paramName] = pid;

                $.ajax({
                    url: url,
                    data: requestData,
                    type: 'GET',
                    success: function(response) {
                        $child.empty().append('<option value="">' + originalPlaceholder + '</option>');
                        
                        // ✨ YENİ: Backend'den 'results', 'options' veya dümdüz 'array' dönebilir, hepsini anlar
                        var items = response.results || response.options || response.data || response;
                        
                        if (Array.isArray(items)) {
                            items.forEach(function(item) { 
                                // id/text veya value/label varyasyonlarını otomatik destekler
                                var val = item.id || item.value;
                                var text = item.text || item.label || item.ad;
                                $child.append(new Option(text, val, false, false)); 
                            });
                        }
                    },
                    error: function() {
                        $child.empty().append('<option value="">' + t('error', 'Yükleme Hatası!') + '</option>');
                    },
                    complete: function() {
                        $child.prop('disabled', false).trigger('change');
                        // Select2 render motorunu uyar ki yeni verileri ekranda göstersin
                        if ($child.hasClass('select2-hidden-accessible')) {
                            $child.trigger('change.select2');
                        }
                    }
                });
            });
        });
    }
	
    // --- 2.9 METİN DÖNÜŞÜMÜ (Text Transform) ---
    function initTextTransform() {
        $('input[data-text-transform]').on('input', function() {
            var type = $(this).data('text-transform');
            var val = $(this).val();
            if (type === 'uppercase') this.value = val.toLocaleUpperCase('tr-TR');
            if (type === 'lowercase') this.value = val.toLocaleLowerCase('tr-TR');
            if (type === 'capitalize') this.value = val.replace(/(?:^|\s)\S/g, function(a) { return a.toLocaleUpperCase('tr-TR'); });
        });
    }


    // 2.10 IMask Entegrasyonu
    function initMasking() {
        if (typeof IMask !== 'undefined') {
            document.querySelectorAll('.phone-mask-tr').forEach(e => IMask(e, { mask: '(000) 000 00 00' }));
            document.querySelectorAll('.credit-card-mask').forEach(e => IMask(e, { mask: '0000 0000 0000 0000' }));
            //document.querySelectorAll('.ip-mask').forEach(e => IMask(e, { mask: '000.000.000.000' }));
            document.querySelectorAll('.ip-mask').forEach(e => {
        const mask = IMask(e, {
        mask: [{
            mask: 'IP',  
            lazy: true, 
            blocks: { 
                IP: { 
                    mask: 'i.i.i.i', 
                    blocks: {
                        i: {  
                            mask: /^[0-9]{0,3}$/, 
                        } 
                    } 
                } 
            } 
        }], 
        dispatch: function (appended, dynamicMasked) { 
            return dynamicMasked.compiledMasks[0]; 
        } 
        });

        // Input sırasında 255 kontrolü
        e.addEventListener('input', function() {
            e.setCustomValidity('');
            
            // Her segmenti kontrol et
            const parts = this.value.split('.');
            const corrected = parts.map(part => {
                if (part === '') return part;
                const num = parseInt(part);
                return (num > 255) ? '255' : part;
            }).join('.');
            
            if (this.value !== corrected) {
                this.value = corrected;
                mask.updateValue();
            }
        });
        
        // Tam IP kontrolü
        e.addEventListener('blur', function() {
            const value = this.value.trim();
            
            if (!value) {
                e.setCustomValidity('');
                return;
            }
            
            const parts = value.split('.');
            
            // 0.0.0.0 kontrolü
            if (value === '0.0.0.0') {
                e.setCustomValidity('0.0.0.0 IP adresi geçersizdir');
                e.reportValidity();
                return;
            }
            
            const isValid = parts.length === 4 && parts.every(part => {
                if (!/^\d+$/.test(part)) return false;
                const num = parseInt(part);
                return num >= 0 && num <= 255;
            });
            
            if (!isValid) {
                e.setCustomValidity('Lütfen geçerli bir IP adresi girin (örn: 192.168.1.1)');
                e.reportValidity();
            } else {
                e.setCustomValidity('');
            }
        });
        });
        }
    }

    // --- 2.11 Medya Kaydedici (Audio/Video) ---
    // 2.11 Medya Kaydedici (Gelişmiş - form-builder.js'den Port Edildi)
    // 2.11 Medya Kaydedici (Python form_field.py ile Tam Uyumlu)
    function initMediaRecorders() {
        // Tarayıcı desteği kontrolü
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.warn('MediaDevices API (Kamera/Mikrofon) bu tarayıcıda veya HTTP protokolünde desteklenmiyor.');
            return;
        }

        // Başlat butonlarını bul (Hem ses hem video için genel seçici)
        // Python tarafı data-action="start" üretiyor.
        $('button[data-action="start"]').off('click.media').on('click.media', async function() {
            var $startBtn = $(this);
            
            // Eğer zaten kayıt yapılıyorsa veya buton pasifse çık
            if ($startBtn.hasClass('disabled')) return;

            // Python'dan gelen attribute'ları al
            var type = $startBtn.data('type'); // 'audio' veya 'video'
            var inputName = $startBtn.data('target'); // 'technician_note' vb.
            
            // İlgili diğer elementleri bul
            var $stopBtn = $('button[data-action="stop"][data-target="' + inputName + '"]');
            var $hiddenInput = $('#' + inputName);
            var $statusText = $startBtn.parent().find('.status-text');
            var $wrapper = $('#wrapper_' + inputName);

            // Element kontrolü
            if (!$stopBtn.length || !$hiddenInput.length) {
                console.error('Durdurma butonu veya input bulunamadı:', inputName);
                return;
            }

            let stream = null;
            let mediaRecorder = null;
            let chunks = [];

            try {
                // İzin iste ve yayını al
                stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: true, 
                    video: type === 'video' // Sadece video ise kamera aç
                });

                // Video ise Canlı Önizlemeyi (Live Preview) Başlat
                if (type === 'video') {
                    var videoPreview = document.getElementById('live_' + inputName);
                    var placeholder = document.getElementById('placeholder_' + inputName);
                    
                    if (videoPreview) {
                        videoPreview.srcObject = stream;
                        videoPreview.style.display = 'block';
                        videoPreview.play(); // Bazı tarayıcılar için play() gerekir
                        if (placeholder) placeholder.style.display = 'none';
                    }
                }

                // Kayıtçıyı Başlat
                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = function(e) {
                    if (e.data.size > 0) chunks.push(e.data);
                };

                mediaRecorder.onstop = function() {
                    // Blob oluştur
                    var blob = new Blob(chunks, { type: type + '/webm' });
                    
                    // Dosyayı Base64'e çevirip Input'a yaz (Sunucuya gönderim için)
                    var reader = new FileReader();
                    reader.onloadend = function() {
                        $hiddenInput.val(reader.result).trigger('input').trigger('change');
                        
                        // Oynatma (Playback) Alanını Oluştur
                        var url = URL.createObjectURL(blob);
                        var $playbackDiv = $('#playback_' + inputName);
                        $playbackDiv.empty();

                        if (type === 'video') {
                            // Kaydedilen videoyu göster
                            $playbackDiv.append('<video src="' + url + '" controls class="w-100 rounded mt-2 shadow-sm" style="max-height: 300px;"></video>');
                            
                            // Canlı önizlemeyi kapat ve gizle
                            var videoPreview = document.getElementById('live_' + inputName);
                            if (videoPreview) {
                                videoPreview.srcObject = null;
                                videoPreview.style.display = 'none';
                            }
                            var placeholder = document.getElementById('placeholder_' + inputName);
                            if (placeholder) placeholder.style.display = 'flex'; // İkonu geri getir
                            
                        } else {
                            // Kaydedilen sesi göster
                            $playbackDiv.append('<audio src="' + url + '" controls class="w-100 mt-2"></audio>');
                        }

                        if ($statusText.length) {
                            $statusText.html('<span class="text-success"><i class="bi bi-check-circle"></i> Kayıt Hazır</span>');
                        }
                    };
                    reader.readAsDataURL(blob);

                    // Donanımı (Kamera/Mikrofon) Kapat
                    if (stream) stream.getTracks().forEach(track => track.stop());
                };

                // Kaydı başlat
                mediaRecorder.start();

                // Buton durumlarını güncelle
                $startBtn.addClass('disabled d-none');
                $stopBtn.removeClass('disabled d-none'); // Durdur butonunu göster
                if ($statusText.length) $statusText.html('<span class="text-danger blink"><i class="bi bi-record-circle"></i> Kaydediliyor...</span>');

                // DURDURMA BUTONU OLAYI (Burada tanımlıyoruz ki scope'daki recorder'a erişsin)
                $stopBtn.off('click.stopMedia').on('click.stopMedia', function() {
                    if (mediaRecorder.state !== 'inactive') {
                        mediaRecorder.stop();
                        
                        // UI Reset
                        $startBtn.removeClass('disabled d-none');
                        $stopBtn.addClass('disabled d-none');
                        $startBtn.html('<i class="bi bi-arrow-counterclockwise"></i> Yeniden Kaydet');
                    }
                });

            } catch (err) {
                console.error('Medya Hatası:', err);
                alert('Kamera/Mikrofon açılamadı.\nLütfen tarayıcı izinlerini kontrol edin.\n\nNot: Bu özellik sadece HTTPS veya Localhost üzerinde çalışır.');
                if ($statusText.length) $statusText.text('Hata: Erişim izni yok.');
            }
        });
    }

    // --- 2.12 Hesap Makinesi (Calc) ---
    function initCalcFields() {
        $(document).on('click', '.calc-opener', function() {
            var id = $(this).data('calc-id');
            $('#'+id).toggle();
        });
        $(document).on('click', '.calc-buttons button', function() {
            var key = $(this).data('key');
            var $display = $(this).closest('.calc-popup').find('.calc-display');
            var val = $display.val();
            
            if(key === '=') {
                try { $display.val(eval(val)); } catch(e) { $display.val('Err'); }
            } else if(key === 'C') {
                $display.val('');
            } else if(key === 'back') {
                $display.val(val.slice(0, -1));
            } else {
                $display.val(val + key);
            }
        });
        $(document).on('click', '.calc-apply', function() {
            var $popup = $(this).closest('.calc-popup');
            var val = $popup.find('.calc-display').val();
            var field = $popup.closest('.calc-container').data('field');
            $('#'+field).val(val).trigger('change');
            $popup.hide();
        });
    }

    // --- 2.13 Text Transform ---
    function initTextTransform() {
        $('input[data-text-transform]').on('input', function() {
            var type = $(this).data('text-transform');
            var val = $(this).val();
            if (type === 'uppercase') this.value = val.toLocaleUpperCase('tr-TR');
            if (type === 'lowercase') this.value = val.toLocaleLowerCase('tr-TR');
            if (type === 'capitalize') this.value = val.replace(/(?:^|\s)\S/g, function(a) { return a.toLocaleUpperCase('tr-TR'); });
        });
    }

    // --- 2.14 Price Range (Slider) ---
    function initPriceRange() {
        if(typeof noUiSlider === 'undefined') return;
        $('.dx-range-dual').each(function(){
            var $el = $(this)[0];
            if($el.noUiSlider) return;
            var min = parseFloat($(this).data('min'));
            var max = parseFloat($(this).data('max'));
            var startMin = parseFloat($(this).data('start-min'));
            var startMax = parseFloat($(this).data('start-max'));
            var name = $(this).data('name');

            noUiSlider.create($el, {
                start: [startMin, startMax],
                connect: true,
                range: { 'min': min, 'max': max },
                step: parseFloat($(this).data('step') || 1)
            });

            $el.noUiSlider.on('update', function(values){
                $('#'+name+'_min').val(values[0]).trigger('change');
                $('#'+name+'_max').val(values[1]).trigger('change');
                $('#'+name+'_min_badge').text(Math.round(values[0]));
                $('#'+name+'_max_badge').text(Math.round(values[1]));
            });
        });
    }

    // 2.15 Rating (Yıldız Puanlama) - EKLENDİ
    function initRatingFields() {
        // Event delegation ile tüm rating-star elementlerini dinle
        $(document).off('click.rating').on('click.rating', '.rating-star', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            var $star = $(this);
            var rating = $star.data('rating');
            var $container = $star.closest('.rating-container');
            var $input = $container.find('input[type="hidden"]');
            
            // 1. Değeri güncelle ve validasyonu tetikle
            $input.val(rating).trigger('change').trigger('input'); 
            
            // 2. Yıldızların görünümünü güncelle (Dolu/Boş)
            $container.find('.rating-star').each(function(index) {
                // index 0'dan başlar, rating 1'den.
                // Örn: Rating 3 ise, index 0, 1, 2 dolu (fas), diğerleri boş (far) olur.
                if (index < rating) {
                    $(this).removeClass('far').addClass('fas'); // Dolu Yıldız
                } else {
                    $(this).removeClass('fas').addClass('far'); // Boş Yıldız
                }
            });
        });
    }

    // --- 2.18 Drawing Field ---
    function initDrawingField() {
        if(typeof fabric === 'undefined') return;
        $('.drawing-field').each(function(){
            var $wrap = $(this);
            var canvasId = $wrap.find('canvas').attr('id');
            var $hidden = $wrap.find('input[type="hidden"]');
            
            var canvas = new fabric.Canvas(canvasId, { isDrawingMode: true });
            canvas.backgroundColor="#fff";
            canvas.freeDrawingBrush.width = 5;
            canvas.freeDrawingBrush.color = "#000000";
            
            if($hidden.val()) {
                fabric.Image.fromURL($hidden.val(), function(img){
                    canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
                });
            }
            
            $wrap.closest('form').on('submit', function(){
                $hidden.val(canvas.toDataURL());
            });
            $wrap.find('[data-action="clear-drawing"]').on('click', function(){
                canvas.clear();
                canvas.backgroundColor="#fff";
            });
        });
    }

    // --- 2.19 YENİ: Tekil Resim Önizleme Fonksiyonu ---
    function initImagePreview() {
        // Event Delegation kullanarak (sonradan eklenenlerde de çalışır)
        $(document).on('change', '.image-upload-field', function(event) {
            const input = event.target;
            const previewId = $(input).data('preview'); // form_field.py bu ID'yi veriyor
            const $previewImg = $('#' + previewId);
            const $clearBtn = $('#' + input.id + '_clear_btn');

            if (input.files && input.files[0]) {
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    $previewImg.attr('src', e.target.result);
                    $previewImg.show(); // Resmi göster
                    $clearBtn.show();   // Sil butonunu göster
                }
                
                reader.readAsDataURL(input.files[0]);
            } else {
                // Dosya seçimi iptal edilirse
                $previewImg.hide();
                $clearBtn.hide();
            }
        });
    }

    // 2.20 Gelişmiş Renk Seçici (Pickr) - EKLENDİ
    function initAdvancedColorPicker() {
        if (typeof Pickr === 'undefined') {
            console.warn('Pickr kütüphanesi yüklü değil (Advanced Color Picker için gerekli).');
            return;
        }

        $('.advanced-color-picker').each(function() {
            const $input = $(this);
            const $wrapper = $input.closest('.color-picker-advanced');
            const $preview = $wrapper.find('.color-preview');
            
            // Eğer daha önce başlatıldıysa atla
            if ($input.data('pickrInit')) return;
            $input.data('pickrInit', true);

            // Başlangıç rengi
            const initialColor = $input.val() || '#42445a';
            $preview.css('background-color', initialColor);

            // Pickr Konfigürasyonu
            const pickr = Pickr.create({
                el: $preview[0], // Tıklanacak eleman (sizin span)
                theme: 'classic', // veya 'monolith', 'nano'
                default: initialColor,
                useAsButton: true, // Span'ı buton gibi kullan
                
                swatches: [
                    'rgba(244, 67, 54, 1)',
                    'rgba(233, 30, 99, 0.95)',
                    'rgba(156, 39, 176, 0.9)',
                    'rgba(103, 58, 183, 0.85)',
                    'rgba(63, 81, 181, 0.8)',
                    'rgba(33, 150, 243, 0.75)',
                    'rgba(3, 169, 244, 0.7)',
                    'rgba(0, 188, 212, 0.7)',
                    'rgba(0, 150, 136, 0.75)',
                    'rgba(76, 175, 80, 0.8)',
                    'rgba(139, 195, 74, 0.85)',
                    'rgba(205, 220, 57, 0.9)',
                    'rgba(255, 235, 59, 0.95)',
                    'rgba(255, 193, 7, 1)'
                ],

                components: {
                    preview: true,
                    opacity: true,
                    hue: true,

                    interaction: {
                        hex: true,
                        rgba: true,
                        input: true,
                        clear: true,
                        save: true
                    }
                },
                
                // Türkçe Çeviriler
                i18n: {
                    'btn:save': 'Kaydet',
                    'btn:clear': 'Temizle'
                }
            });

            // Olaylar (Events)
            
            // 1. Pickr'dan renk seçilince Input'a yaz
            pickr.on('save', (color, instance) => {
                const colorHex = color ? color.toHEXA().toString() : '';
                $input.val(colorHex).trigger('change'); // Form validasyonu için trigger
                $preview.css('background-color', colorHex);
                instance.hide();
            });

            // Renk değişirken canlı önizleme (Opsiyonel)
            pickr.on('change', (color, source, instance) => {
                const colorHex = color ? color.toHEXA().toString() : '';
                $preview.css('background-color', colorHex);
                // Input'a anlık yazmak isterseniz:
                // $input.val(colorHex);
            });

            // 2. Input elle değiştirilirse Pickr'ı güncelle
            $input.on('input change', function() {
                const val = $(this).val();
                if (val) {
                    pickr.setColor(val);
                    $preview.css('background-color', val);
                }
            });
        });
    }

	// 2.21 Select2 Başlatıcı (AJAX Destekli)
    function initializeSelect2(container) {
        if (typeof $ === 'undefined' || !$.fn.select2) return;

        var $selects = container ? $(container).find('.select2-field') : $('.select2-field');

        $selects.each(function() {
            var $el = $(this);
            if ($el.hasClass('select2-hidden-accessible')) return;

            var config = {
                theme: 'bootstrap-5',
                width: '100%',
                placeholder: $el.data('placeholder') || 'Seçiniz...',
                allowClear: true,
                language: 'tr'
            };
            
            // --- AJAX DESTEĞİ EKLENDİ ---
            // Eğer elementte data-ajax-url varsa, konfigürasyonu değiştir
            if ($el.data('ajax-url')) {
                config.ajax = {
                    url: $el.data('ajax-url'),
                    dataType: 'json',
                    delay: 250, // Klavye vuruş beklemesi (ms)
                    data: function (params) {
                        return {
                            term: params.term, // Arama kelimesi
                            page: params.page || 1
                        };
                    },
                    processResults: function (data, params) {
						params.page = params.page || 1;
						
						// Güvenlik kontrolü: API pagination göndermediyse false say
						var hasMore = (data.pagination && data.pagination.more) ? data.pagination.more : false;
						
						return {
							results: data.results,
							pagination: {
								more: hasMore
							}
						};
					},
                    cache: true
                };
                // En az 1 karakter girince aramaya başla (0 yaparsanız tıklar tıklamaz getirir)
                config.minimumInputLength = 0; 
            }
            // ---------------------------

            if ($el.data('tags')) {
                config.tags = true;
                config.tokenSeparators = [','];
            }

            $el.select2(config);

            // Validasyon entegrasyonu (Değişmedi)
            $el.on('change', function() {
                if ($(this).val()) {
                    $(this).removeClass('is-invalid').addClass('is-valid');
                    $(this).next('.select2-container').find('.select2-selection').removeClass('is-invalid border-danger');
                }
            });
        });
    }

    // 2.22 Single Slider (Tekli Kaydırma Çubuğu) - EKLENDİ
    function initSingleSlider() {
        if (typeof noUiSlider === 'undefined') {
            console.warn('noUiSlider kütüphanesi yüklü değil.');
            return;
        }

        $('.dx-slider').each(function() {
            var $slider = $(this);
            var sliderElem = $slider[0];

            // Daha önce başlatıldıysa atla
            if ($slider.data('sliderInit')) return;
            $slider.data('sliderInit', true);

            var name = $slider.attr('id').replace('slider_', ''); // ID'den ismi al
            var min = parseFloat($slider.data('min') || 0);
            var max = parseFloat($slider.data('max') || 100);
            var step = parseFloat($slider.data('step') || 1);
            var start = parseFloat($slider.data('start') || min);
            var tooltips = $slider.data('tooltips') === true;

            var $input = $('#' + name);
            var $display = $('#display_' + name);

            noUiSlider.create(sliderElem, {
                start: [start],
                connect: [true, false], // Sol tarafı dolu göster
                range: {
                    'min': min,
                    'max': max
                },
                step: step,
                // Tooltip ayarı: True ise göster, formatla
                tooltips: tooltips ? {
                    to: function(val) { return Math.round(val); }
                } : false,
                pips: $slider.data('pips') ? {
                    mode: 'count',
                    values: 5,
                    density: 4
                } : null
            });

            // Değer değiştiğinde
            sliderElem.noUiSlider.on('update', function(values, handle) {
                var value = parseFloat(values[0]);
                
                // 1. Gizli inputu güncelle
                $input.val(value).trigger('change'); // Validasyonu tetikle
                
                // 2. Görünen değeri güncelle
                if ($display.length) {
                    $display.text(Math.round(value));
                }
            });
        });
    }

    // 2.23 Geolocation (GPS Konum Alma) - EKLENDİ
    function initGeolocation() {
        $(document).off('click.geo').on('click.geo', '[data-action="get-location"]', function() {
            var $btn = $(this);
            var inputId = $btn.data('input');
            var $input = $('#' + inputId);
            
            if (!navigator.geolocation) {
                alert('Tarayıcınız konum servisini desteklemiyor.');
                return;
            }
            
            $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Alınıyor...');
            
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    var lat = position.coords.latitude.toFixed(6);
                    var lng = position.coords.longitude.toFixed(6);
                    $input.val(lat + ', ' + lng).trigger('change'); // Validasyonu tetikle
                    $btn.prop('disabled', false).html('<i class="fas fa-check"></i> Güncelle');
                },
                function(error) {
                    var msg = 'Konum alınamadı.';
                    if(error.code == 1) msg = 'Konum izni reddedildi.';
                    else if(error.code == 2) msg = 'Konum bulunamadı.';
                    else if(error.code == 3) msg = 'Zaman aşımı.';
                    
                    alert(msg);
                    $btn.prop('disabled', false).html('<i class="fas fa-exclamation-triangle"></i> Tekrar Dene');
                }
            );
        });
    }

    // 2.24 Multi-Field (Dinamik Liste Yönetimi)
    function initMultiField() {
  
        // 1. Satır Ekleme
        $(document).off('click.addMulti').on('click.addMulti', '.btn-add-row', function() {
            var $wrapper = $(this).closest('.multi-field-wrapper');
            var template = $wrapper.find('template.row-template')[0];
            var $list = $wrapper.find('.multi-field-list');
            
            if (!template) return;

            // Şablonu kopyala
            var $newRow = $(template.content.cloneNode(true)).children();
            
            // Listeye ekle
            $list.append($newRow);
            
            // --- YENİ SATIR İÇİN WIDGET'LARI BAŞLAT ---
            
            // A) Select2 Başlat
            if (typeof initializeSelect2 === 'function') {
                initializeSelect2($newRow);
            }
            
            // B) Maskeleme (Telefon, Para vb.)
            if (typeof initMasking === 'function') {
                // Performans için sadece yeni satırı hedefleyebiliriz ama 
                // IMask mevcutları bozmadığı için genel çağırabiliriz.
                initMasking();
            }
            
            // C) Para Formatı (Manuel formatter)
            if (typeof initParaFormat === 'function') {
                // Bu fonksiyon genellikle document.ready'de çalışır,
                // yeni elementler için event listener'ları tekrar bağlamak gerekebilir.
                // En temizi, fonksiyonu yeni element üzerinde çağırmaktır.
                $newRow.find('.fiyat-input, input[data-currency="true"]').each(function(){
                    // initParaFormat mantığını buraya taşıyabilir veya fonksiyonu modifiye edebiliriz.
                    // Şimdilik input eventini manuel tetikleyelim.
                    $(this).trigger('input');
                });
            }
        });

        // 2. Satır Silme
        $(document).off('click.removeMulti').on('click.removeMulti', '.btn-remove-row', function() {
            $(this).closest('.multi-field-row').remove();
        });
    }

    // 2.25 Date Range (Tarih Aralığı) - EKLENDİ
    function initDateRange() {
        $('.date-range').each(function() {
            var $wrap = $(this);
            // Inputları bul
            var $start = $wrap.find('input[name$="_start"]');
            var $end = $wrap.find('input[name$="_end"]');
            var $errDiv = $wrap.find('.invalid-feedback'); // Hata mesajı alanı
            var $presets = $wrap.find('[data-preset]');    // Hızlı seçim butonları

            // Yardımcı: Date objesini YYYY-MM-DD stringine çevir
            function formatDate(d) {
                var month = '' + (d.getMonth() + 1);
                var day = '' + d.getDate();
                var year = d.getFullYear();

                if (month.length < 2) month = '0' + month;
                if (day.length < 2) day = '0' + day;

                return [year, month, day].join('-');
            }

            // Validasyon ve Kısıtlama Mantığı
            function checkDates() {
                var sVal = $start.val();
                var eVal = $end.val();

                // 1. Min/Max sınırlarını dinamik ayarla
                if (sVal) $end.attr('min', sVal); else $end.removeAttr('min');
                if (eVal) $start.attr('max', eVal); else $start.removeAttr('max');

                // 2. Hata kontrolü (Başlangıç > Bitiş)
                if (sVal && eVal && sVal > eVal) {
                    $start.addClass('is-invalid');
                    $end.addClass('is-invalid');
                    $errDiv.removeClass('d-none').show();
                } else {
                    $start.removeClass('is-invalid');
                    $end.removeClass('is-invalid');
                    $errDiv.addClass('d-none').hide();
                }
            }

            // Hızlı Seçim Butonları (Presets)
            $presets.on('click', function(e) {
                e.preventDefault(); // Form submit olmasın
                var type = $(this).data('preset');
                var today = new Date();
                var start = new Date();
                var end = new Date();

                switch(type) {
                    case 'today':
                        // Başlangıç ve Bitiş = Bugün
                        break; // Zaten new Date() bugün
                    case 'yesterday':
                        start.setDate(today.getDate() - 1);
                        end.setDate(today.getDate() - 1);
                        break;
                    case 'last7':
                        start.setDate(today.getDate() - 6);
                        // End zaten bugün
                        break;
                    case 'thisMonth':
                        start = new Date(today.getFullYear(), today.getMonth(), 1);
                        end = new Date(today.getFullYear(), today.getMonth() + 1, 0); // Ayın son günü
                        break;
                    case 'lastMonth':
                        start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                        end = new Date(today.getFullYear(), today.getMonth(), 0);
                        break;
                }

                // Inputlara yaz
                $start.val(formatDate(start));
                $end.val(formatDate(end));
                
                // Kontrolü tetikle
                checkDates();
            });

            // Elle değişiklik yapıldığında kontrol et
            $start.on('change input', checkDates);
            $end.on('change input', checkDates);
        });
    }

    // 2.26 Autocomplete (Otomatik Tamamlama - Bootstrap 5 Style)
    function initAutocomplete() {
        // Stil ekle (Dropdown pozisyonu için)
        if (!$('#autocomplete-style').length) {
            $('head').append('<style id="autocomplete-style">.autocomplete-suggestions { max-height: 200px; overflow-y: auto; cursor: pointer; }</style>');
        }

        $('.autocomplete-field').each(function() {
            var $input = $(this);
            var url = $input.data('source-url'); // Python'dan gelen API adresi
            var method = $input.data('source-method') || 'GET';
            
            // Dropdown menüsü oluştur (Bootstrap yapısı)
            var $dropdown = $('<ul class="dropdown-menu w-100 autocomplete-suggestions"></ul>');
            $input.parent().addClass('dropdown').append($dropdown);
            
            var debounceTimer;

            $input.on('input', function() {
                var query = $(this).val();
                clearTimeout(debounceTimer);
                
                if (query.length < 2) {
                    $dropdown.removeClass('show');
                    return;
                }

                debounceTimer = setTimeout(function() {
                    // AJAX İsteği (Veya statik veri)
                    if (url) {
                        $input.addClass('is-loading'); // Loading ikonu eklenebilir
                        $.ajax({
                            url: url,
                            method: method,
                            data: { q: query },
                            success: function(response) {
                                // Response formatı: [{value: '1', label: 'Elma'}, ...] veya ['Elma', 'Armut']
                                renderSuggestions(response);
                            },
                            complete: function() {
                                $input.removeClass('is-loading');
                            }
                        });
                    }
                }, 300);
            });

            function renderSuggestions(data) {
                $dropdown.empty();
                
                if (!data || data.length === 0) {
                    $dropdown.removeClass('show');
                    return;
                }

                data.forEach(function(item) {
                    var label = item.label || item.text || item;
                    var value = item.value || item.id || item;
                    
                    var $li = $('<li><a class="dropdown-item" href="#" data-val="' + value + '">' + label + '</a></li>');
                    $dropdown.append($li);
                });

                $dropdown.addClass('show');
            }

            // Seçim Yapma
            $dropdown.on('click', '.dropdown-item', function(e) {
                e.preventDefault();
                var text = $(this).text();
                // var val = $(this).data('val'); // İstenirse ID gizli bir inputa yazılabilir
                
                $input.val(text);
                $dropdown.removeClass('show');
                $input.trigger('change'); // Validasyon için
            });

            // Dışarı tıklayınca kapat
            $(document).on('click', function(e) {
                if (!$(e.target).closest($input.parent()).length) {
                    $dropdown.removeClass('show');
                }
            });
        });
    }

    // 2.27 Search & Button Actions
    function initSearchAndButtons() {
        // Arama Kutusu (Search) Temizleme Butonu
        $('input[type="search"]').on('input', function() {
            // HTML5 search inputlarında (x) işareti tarayıcı tarafından genelde konur.
            // Biz özel bir temizleme butonu eklediysek onu yönetelim.
            var $input = $(this);
            var $clearBtn = $input.parent().find('.btn-clear-search');
            
            if ($input.val().length > 0) $clearBtn.show();
            else $clearBtn.hide();
        });

        // Buton Tıklama (Genel Action Handler)
        $('button[data-btn-action]').on('click', function(e) {
            var action = $(this).data('btn-action');
            
            if (action === 'reset') {
                $(this).closest('form')[0].reset();
                // Select2 ve diğer widgetları da sıfırla
                $('.select2-field').val(null).trigger('change');
                showToast('Form temizlendi.', 'info');
            }
            else if (action === 'print') {
                window.print();
            }
            else if (action === 'ajax-check') {
                // Özel bir işlem örneği
                alert('Buton tıklandı! ID: ' + this.id);
            }
        });
    }

    // 2.28 Modal Düzeltmeleri (Select2 Focus Sorunu İçin)
    function initModalFixes() {
        // Modal açıldığında içindeki inputa odaklan
        $('.modal').on('shown.bs.modal', function () {
            $(this).find('input:visible:first').focus();
            
            // Modal içindeki Select2'leri yeniden tetikle (Görünürlük sorunu varsa)
            // dropdownParent ayarı Select2 config'de yapılmalıdır, 
            // ancak burada manuel düzeltme gerekirse yapılabilir.
        });

        // Select2'nin Modal içinde çalışması için "dropdownParent" ayarı kritik öneme sahiptir.
        // initializeSelect2 fonksiyonunu modifiye ederek modal kontrolü ekleyelim.
        // (Aşağıdaki notu okuyun)
    }

    // 2.29 Uzaktan Benzersizlik Kontrolü (Remote Unique Check)
    function initUniqueCheck() {
        // 'data-unique-check' özelliği olan inputlar için çalışır
        $(document).off('blur.unique').on('blur.unique', 'input[data-unique-check]', function() {
            var $input = $(this);
            var val = $input.val().trim();
            var url = $input.data('unique-check'); // API Adresi
            
            // Boşsa veya salt okunursa (edit modu) kontrol etme
            if (val === '' || $input.prop('readonly')) return;

            // Küçük bir yükleniyor ikonu gösterelim (Opsiyonel)
            var originalIcon = null;
            var $iconContainer = $input.parent().find('.input-group-text i');
            if($iconContainer.length) {
                originalIcon = $iconContainer.attr('class');
                $iconContainer.attr('class', 'spinner-border spinner-border-sm text-secondary');
            }

            $.ajax({
                url: url,
                method: 'GET',
                data: { kod: val },
                success: function(response) {
                    if (response.exists) {
                        // KAYIT VARSA: Hata Göster
                        $input.addClass('is-invalid').removeClass('is-valid');
                        
                        // Varsa eski hatayı sil, yenisini ekle
                        $input.closest('div').find('.invalid-feedback.unique-error').remove();
                        
                        // Input'un sonuna hata mesajı ekle
                        var msg = response.message || 'Bu kayıt zaten mevcut.';
                        var $parent = $input.closest('.input-group').length ? $input.closest('.input-group') : $input;
                        $parent.after('<div class="invalid-feedback unique-error d-block">' + msg + '</div>');
                    } else {
                        // KAYIT YOKSA: Temizle / Onayla
                        $input.removeClass('is-invalid').addClass('is-valid');
                        $input.closest('div').find('.invalid-feedback.unique-error').remove();
                    }
                },
                complete: function() {
                    // İkonu geri yükle
                    if(originalIcon) $iconContainer.attr('class', originalIcon);
                }
            });
        });
        
        // Kullanıcı tekrar yazmaya başladığında hatayı sil
        $(document).on('input', 'input[data-unique-check]', function() {
            $(this).removeClass('is-invalid');
            $(this).closest('div').find('.invalid-feedback.unique-error').remove();
        });
    }

    // 2.30 Otomatik Numara Getirici (Entegre Edilmiş Hali)
    function initAutoNumber() {
        const autoFields = document.querySelectorAll('input[data-auto-fetch]');
        
        if (autoFields.length === 0) return;

        autoFields.forEach(function(input) {
            // Eğer input zaten doluysa (Edit modu) işlem yapma
            if (input.value.trim() !== "") {
                // Dolu olduğu için validasyonu tetikle (Yeşil olsun)
                input.dispatchEvent(new Event('input'));
                return;
            }

            const url = input.getAttribute('data-auto-fetch');
            const spinnerId = input.id + "_spinner";
            const spinner = document.getElementById(spinnerId);

            // Spinner göster
            if(spinner) spinner.style.display = "block";

            // Validasyon: Şu an boş olduğu için hata verebilir, geçici olarak ignore edebiliriz
            // ama fetch bitince düzelecek.

            fetch(url)
                .then(response => {
                    if (!response.ok) throw new Error("API Hatası");
                    return response.json();
                })
                .then(data => {
                    // API'den gelen değeri bul
                    const val = data.code || data.next_code || data.value || data.id;
                    
                    if (val) {
                        input.value = val;
                        
                        // ✅ KRİTİK NOKTA: Değer atandıktan sonra validasyonu tetikle
                        // Bu sayede input "Required" hatasından kurtulup "Valid" (Yeşil) olur.
                        input.dispatchEvent(new Event('input'));
                        input.dispatchEvent(new Event('change'));

                        // Görsel Efekt
                        input.style.transition = "background-color 0.5s";
                        input.style.backgroundColor = "#d4edda"; // Yeşilimsi
                        setTimeout(() => {
                            // Readonly ise griye, değilse beyaza dön
                            input.style.backgroundColor = input.hasAttribute('readonly') ? "#e9ecef" : "#ffffff";
                        }, 1000);
                    }
                })
                .catch(err => {
                    console.error("Otomatik numara alınamadı:", err);
                    input.placeholder = "Numara alınamadı!";
                    // Hata durumunda validasyonu tetikle ki kırmızı yansın
                    input.dispatchEvent(new Event('input'));
                })
                .finally(() => {
                    if(spinner) spinner.style.display = "none";
                });
        });
    }

    // 2.31 Bağımlı Alan (Cascading Select) Yönetimi - YENİ
    function initDependentFields() {
        // data-source attribute'u olan ve depends_on içeren selectleri bul
        $('select[data-source-url]').each(function() {
            const $childSelect = $(this);
            const parentName = $childSelect.data('dependent-parent'); // "sehir_id"
            const url = $childSelect.data('source-url');              // "/cari/api/get-ilceler"
            
            if (!parentName || !url) return;

            // Parent (Tetikleyici) inputu bul
            const $parentInput = $('[name="' + parentName + '"]');

            // Tetikleyici değiştiğinde çalışacak fonksiyon
            $parentInput.on('change', function() {
                const parentValue = $(this).val();

                // 1. Child'ı temizle ve disable et
                $childSelect.empty().append('<option value="">Seçiniz...</option>').prop('disabled', true);
                
                // Select2 ise placeholder göster
                if ($childSelect.hasClass('select2-hidden-accessible')) {
                    $childSelect.trigger('change'); 
                }

                // 2. Eğer parent boşsa çık (Child boş kalsın)
                if (!parentValue) return;

                // 3. API'den veri çek
                // Spinner göster (Select2 varsa container'ına ekle)
                // ... (Opsiyonel spinner kodu) ...

                $.ajax({
                    url: url,
                    type: 'GET',
                    data: { [parentName]: parentValue }, // { sehir_id: 34 }
                    success: function(response) {
                        // Response formatı: [{id: 1, text: 'Adana'}, ...] olmalı
                        
                        if (Array.isArray(response)) {
                            response.forEach(function(item) {
                                // API'den gelen id ve text/ad alanlarını eşle
                                const val = item.id || item.value || item.kod;
                                const text = item.text || item.ad || item.name || item.label;
                                
                                const option = new Option(text, val, false, false);
                                $childSelect.append(option);
                            });
                        }
                        
                        // 4. Child'ı aktif et
                        $childSelect.prop('disabled', false);
                        
                        // Select2 güncelle
                        if ($childSelect.hasClass('select2-hidden-accessible')) {
                            $childSelect.trigger('change');
                        }
                    },
                    error: function(err) {
                        console.error("Bağımlı veri çekilemedi:", err);
                        showToast("Veri yüklenirken hata oluştu.", "error");
                    }
                });
            });
        });
    }

	// 2.32 Gelişmiş Klavye Kontrolleri (Master-Detail Özel - DÜZELTİLMİŞ)
	function initKeyboardActions() {
    
	// ==============================================================
	// 🔥 2.33 ASYNC (AJAX) ANLIK DOĞRULAMA MOTORU
	// ==============================================================
	function initAsyncValidation() {
    $('input[data-async-val-url]').on('input', function() {
        var $input = $(this);
        var url = $input.data('async-val-url');
        var debounceMs = $input.data('async-val-debounce') || 500;
        
        // ✨ YENİ: Python'dan gelen table ve exclude_id gibi parametreleri oku
        var extraParams = $input.data('async-val-params') || {};
        
        clearTimeout($input.data('async-timer'));
        
        var val = $input.val().trim();
        if (!val) {
            $input.removeClass('is-invalid is-valid async-loading');
            $input.siblings('.invalid-feedback').text(''); // Yazıyı da temizle
            return;
        }

        var timer = setTimeout(function() {
            // ✨ YENİ: API'nin beklediği kusursuz JSON paketini hazırla
            var requestData = Object.assign({}, extraParams);
            requestData['value'] = val;
            requestData['field'] = requestData['field'] || $input.attr('name');

            $.ajax({
                url: url,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(requestData),
                headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content },
                success: function(res) {
                    if (res.valid) {
                        $input.removeClass('is-invalid').addClass('is-valid');
                        $input.siblings('.invalid-feedback').text('');
                    } else {
                        $input.removeClass('is-valid').addClass('is-invalid');
                        let $feedback = $input.siblings('.invalid-feedback');
                        if($feedback.length === 0) {
                            $feedback = $('<div class="invalid-feedback fw-bold"></div>');
                            $input.after($feedback);
                        }
                        $feedback.text(res.message || 'Geçersiz veri.');
                    }
                },
                error: function(xhr) {
                    console.error("Async validasyon hatası (Eksik parametre olabilir):", xhr.responseText);
                }
            });
        }, debounceMs);
        
        $input.data('async-timer', timer);
    });
}

	// Sayfa yüklendiğinde motoru çalıştır (Eğer mevcut document.ready varsa içine de koyabilirsin)
$(document).ready(function() {
    initAsyncValidation();
});

    function focusNextInput($currentElement) {
        var $row = $currentElement.closest('tr');
        
        // Satırdaki tüm geçerli inputları bul (Select2'nin gizli select'i dahil)
        var $allInputs = $row.find('input, select, textarea').filter(function() {
            var $el = $(this);
            if ($el.is('[readonly]') || $el.is('[disabled]') || $el.attr('type') === 'hidden') return false;
            return $el.is(':visible') || $el.hasClass('select2-hidden-accessible');
        });

        var idx = $allInputs.index($currentElement);

        if (idx > -1 && idx < $allInputs.length - 1) {
            // AYNI SATIRDA SONRAKİNE GİT
            var $next = $allInputs.eq(idx + 1);
            if ($next.hasClass('select2-hidden-accessible')) {
                $next.select2('open'); 
            } else {
                $next.focus().select();
            }
        } else {
            // SATIR BİTTİ, ALT SATIRA GEÇ
            var $nextRow = $row.next('tr');
            if ($nextRow.length) {
                var $nextRowFirst = $nextRow.find('input:visible, select').filter(function() {
                     return $(this).is(':visible') || $(this).hasClass('select2-hidden-accessible');
                }).not('[readonly], [disabled]').first();
                
                if ($nextRowFirst.length) {
                    if ($nextRowFirst.hasClass('select2-hidden-accessible')) {
                        $nextRowFirst.select2('open');
                    } else {
                        $nextRowFirst.focus().select();
                    }
                }
            }
        }
    }

    // --- A) OK TUŞLARI (Yukarı/Aşağı) ---
    $(document).on('keydown', '.master-detail-container table tbody input', function(e) {
        if (e.which !== 38 && e.which !== 40) return;
        if ($(this).parent().find('.autocomplete-suggestions.show').length > 0) return; // Autocomplete varsa karışma

        var $currentInput = $(this);
        var $currentTd = $currentInput.closest('td');
        var $currentRow = $currentTd.closest('tr');
        var columnIndex = $currentTd.index();

        var $targetRow = (e.which === 38) ? $currentRow.prev('tr') : $currentRow.next('tr');

        if ($targetRow.length) {
            e.preventDefault();
            // Hedef hücredeki ilk input/select'i bul
            var $targetCell = $targetRow.find('td').eq(columnIndex);
            var $targetInput = $targetCell.find('input:visible, select').filter(function() {
                return $(this).is(':visible') || $(this).hasClass('select2-hidden-accessible');
            }).first();

            if ($targetInput.length) {
                if ($targetInput.hasClass('select2-hidden-accessible')) {
                    $targetInput.select2('open');
                } else {
                    $targetInput.focus().select();
                }
            }
        }
    });

    // --- B) ENTER (Inputlar İçin) ---
    $(document).on('keydown', '.master-detail-container table tbody input', function(e) {
        if (e.which === 13) { 
            e.preventDefault(); 
            focusNextInput($(this));
        }
    });

    // --- C) SELECT2 KAPANDIĞINDA ---
    $(document).on('select2:close', '.master-detail-container table tbody select', function(e) {
        var $self = $(this);
        setTimeout(function(){
            focusNextInput($self);
        }, 50);
    });

    // --- D) F2 TUŞU (Yeni Satır) ---
    $(document).on('keydown', function(e) {
        if (e.which === 113) { // F2
            e.preventDefault();
            var $table = $('.master-detail-container:visible').first();
            if ($table.length) mdAddRow($table.data('name'));
        }
    });
}

// 2.33 Global Form Navigasyonu (Tam Düzeltilmiş Versiyon)
function initGlobalFormNavigation() {
    
    // Yardımcı: Bir sonraki inputa git
    function jumpToNextField($currentElement) {
        var $form = $currentElement.closest('form');
        if ($form.length === 0 || $currentElement.closest('.master-detail-container').length > 0) return;

        // 1. Formdaki tüm potansiyel adayları topla
        var $candidates = $form.find('input, select, textarea, button:not([type="submit"])');
        
        // 2. Filtreleme: Sadece odaklanılabilir olanları al
        var $focusable = $candidates.filter(function() {
            var $el = $(this);
            
            // Devre dışı, readonly veya hidden type ise atla
            if ($el.is('[disabled]') || $el.is('[readonly]') || $el.attr('type') === 'hidden') {
                return false;
            }
            // Tabindex -1 ise atla
            if ($el.attr('tabindex') === '-1') return false;

            // Görünür mü? VEYA Select2 mi? (Select2 orjinal select'i gizler ama o bizim için geçerlidir)
            return $el.is(':visible') || $el.hasClass('select2-hidden-accessible');
        });

        // 3. Sıradaki elemanı bul
        var index = $focusable.index($currentElement);
        
        if (index > -1 && index < $focusable.length - 1) {
            var $next = $focusable.eq(index + 1);
            
            // --- GEÇİŞ MANTIĞI ---
            if ($next.hasClass('select2-hidden-accessible')) {
                // Eğer sıradaki Select2 ise: AÇ
                $next.select2('open'); 
            } else {
                // Normal Input ise: ODAKLAN ve SEÇ
                $next.focus();
                if ($next.is('input')) {
                    setTimeout(function(){ $next.select(); }, 10);
                }
            }
        } else {
            // Form sonu (Opsiyonel: Kaydet butonuna git)
            // $form.find('[type="submit"]').first().focus();
        }
    }

    // --- A) NORMAL INPUTLARDA ENTER ---
    $(document).on('keydown', 'form input:not(.select2-search__field)', function(e) {
        if (e.which === 13) { // Enter
            if ($(this).closest('.master-detail-container').length > 0) return; // Master-Detail'e karışma
            e.preventDefault();
            jumpToNextField($(this));
        }
    });

    // --- B) SELECT2 KAPANDIĞINDA (Seçim Yapılınca veya Enter'a Basılınca) ---
    $(document).on('select2:close', 'select', function(e) {
        if ($(this).closest('.master-detail-container').length > 0) return; // Master-Detail'e karışma

        var $self = $(this);
        // Select2 kapanırken focus body'ye düşebilir, bunu yakalayıp yönlendiriyoruz.
        setTimeout(function() {
            jumpToNextField($self);
        }, 100); 
    });
}


    // ==========================================
    // INPUT FORMATLAMA FONKSİYONLARI
    // ==========================================
    const FORMATTERS = {

        uppercase: (value) => {
            return { formatted: value.toLocaleUpperCase('tr-TR') };
        },
    
        // 1. Türkçe Küçük Harf
        lowercase: (value) => {
            return { formatted: value.toLocaleLowerCase('tr-TR') };
        },

        // 2. Türkçe Büyük Harf (Mevcut uppercase yerine bunu kullanın)
        uppercaseTR: (value) => {
            return { formatted: value.toLocaleUpperCase('tr-TR') };
        },

        // 3. Baş Harfleri Büyüt (Ad Soyad için)
        capitalize: (value) => {
            // Sadece harfleri ve boşlukları koru, baş harfleri büyüt
            let formatted = value.replace(/(?:^|\s|["'([{])+\S/g, match => match.toLocaleUpperCase('tr-TR'));
            return { formatted: formatted };
        },

        integer: (value) => {
            return { formatted: value.replace(/\D/g, '') };
        },

        // 5. Saat Formatı (HH:MM)
        time: (value) => {
            const digits = value.replace(/\D/g, '').substring(0, 4);
            let formatted = '';
            if (digits.length > 0) formatted = digits.substring(0, 2);
            if (digits.length > 2) formatted += ':' + digits.substring(2, 4);
            
            // Basit mantık kontrolü (24 saat ve 60 dakika sınırı)
            // İlk 2 hane 23'ten büyükse düzeltme mantığı eklenebilir ama maskeleme için bu yeterli.
            return { formatted, digits };
        },
        
        // 2. Ondalıklı Sayı (Genel Sayı Girişi)
        // Nokta veya virgüle izin verir, harfleri siler.
        number: (value) => {
            // Sadece rakam, nokta, virgül ve eksi işaretine izin ver
            let formatted = value.replace(/[^\d.,-]/g, '');
            
            // Eksi işareti sadece başta olabilir
            if (formatted.lastIndexOf('-') > 0) {
                formatted = formatted.replace(/-/g, '');
            }
            
            // Birden fazla nokta/virgül engelleme (Basit kontrol)
            // (Daha gelişmişi currency'de var, bu basit giriş için yeterli)
            return { formatted: formatted };
        },

        phoneTR: (value) => {
            let digits = value.replace(/\D/g, '');
            if (digits.startsWith('90')) digits = digits.substring(2);
            if (digits.startsWith('0')) digits = digits.substring(1);
            digits = digits.substring(0, 10);

            let formatted = '';
            if (digits.length > 0) formatted = '(' + digits.substring(0, 3);
            if (digits.length >= 3) formatted += ') ' + digits.substring(3, 6);
            if (digits.length >= 6) formatted += ' ' + digits.substring(6, 8);
            if (digits.length >= 8) formatted += ' ' + digits.substring(8, 10);

            return { formatted, digits };
        },

        creditCard: (value) => {
            // Sadece rakamları al ve maksimum 16 hane ile sınırla
            const digits = String(value).replace(/\D/g, '').substring(0, 16);
            
            // 4'erli gruplara ayır
            const parts = [];
            for (let i = 0; i < digits.length; i += 4) {
                parts.push(digits.substring(i, i + 4));
            }
            
            // Aralarına boşluk koyarak birleştir ve döndür
            return { formatted: parts.join(' ') };
        },

        iban: (value) => {
            const cleaned = value.toUpperCase().replace(/[^A-Z0-9]/g, '').substring(0, 26);
            const formatted = cleaned.replace(/(.{4})/g, '$1 ').trim();
            return { formatted, cleaned };
        },

        tckn: (value) => {
            const digits = value.replace(/\D/g, '').substring(0, 11);
            return { formatted: digits, digits };
        },

        vkn: (value) => {
            const digits = value.replace(/\D/g, '').substring(0, 10);
            return { formatted: digits, digits };
        },

        plate: (value) => {
            const cleaned = value.toUpperCase().replace(/[^A-Z0-9]/g, '').substring(0, 8);
            
            // Basit ayırma mantığı (İl + Harf + Sayı)
            let formatted = cleaned;
            const match = cleaned.match(/^(\d{1,2})([A-Z]{1,3})(\d{1,4})$/);
            if (match) {
                formatted = `${match[1]} ${match[2]} ${match[3]}`;
            } else if (cleaned.length > 2) {
                 // Henüz tam eşleşmediyse en azından ili ayır
                 formatted = cleaned.substring(0, 2) + ' ' + cleaned.substring(2);
            }

            return { formatted, cleaned };
        },

        date: (value) => {
            // EĞER DEĞER NATIVE DATE FORMATINDAYSA (YYYY-MM-DD) DOKUNMA!
            if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
                return { formatted: value };
            }

            // Sadece TEXT girişler için formatlama (DD.MM.YYYY)
            const digits = value.replace(/\D/g, '').substring(0, 8);
            let formatted = '';
            if (digits.length > 0) formatted = digits.substring(0, 2);
            if (digits.length > 2) formatted += '.' + digits.substring(2, 4);
            if (digits.length > 4) formatted += '.' + digits.substring(4, 8);
            return { formatted, digits };
        },

        currency: (value, decimals = 2) => {
            // Boşluk hatası düzeltildi: (? ! $) -> (?!$)
            const cleaned = value.replace(/[^\d,]/g, '');
            const parts = cleaned.split(',');
            
            // Başındaki gereksiz sıfırları sil
            let integerPart = parts[0].replace(/^0+(?!$)/, '') || '0';
            const decimalPart = parts[1] ? parts[1].substring(0, decimals) : '';

            // Binlik ayırıcı (.)
            integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

            let formatted = integerPart;
            if (parts.length > 1 || value.includes(',')) {
                formatted += ',' + decimalPart;
            }

            return { formatted, value: parts[0] + '.' + decimalPart };
        }
    };

    // ==========================================
    // TEMEL VALİDASYON KURALLARI
    // ==========================================
    const RULES = {
        required: (value) => {
            if (value === null || value === undefined) return false;
            if (typeof value === 'string') return value.trim().length > 0;
            if (Array.isArray(value)) return value.length > 0;
            return true;
        },
        minLength: (value, params) => {
            if (!value) return true;
            const cleaned = String(value).replace(/[\s\-\(\)\.]/g, '');
            return cleaned.length >= parseInt(params.min);
        },
        maxLength: (value, params) => {
            if (!value) return true;
            return String(value).length <= parseInt(params.max);
        },
        min: (value, params) => {
            if (!value && value !== 0) return true;
            const numValue = parseFloat(String(value).replace(/\./g, '').replace(',', '.'));
            return !isNaN(numValue) && numValue >= parseFloat(params.min);
        },
        max: (value, params) => {
            if (!value && value !== 0) return true;
            const numValue = parseFloat(String(value).replace(/\./g, '').replace(',', '.'));
            return !isNaN(numValue) && numValue <= parseFloat(params.max);
        },
        email: (value) => {
            if (!value) return true;
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value).toLowerCase());
        },
        url: (value) => {
            if (!value) return true;
            try {
                new URL(value.includes('://') ? value : `https://${value}`);
                return true;
            } catch (e) {
                return false;
            }
        },
        ip: (value) => {
            if (!value) return true;
            // 0-255 arası 4 grup kontrolü
            return /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/.test(value);
        },
        pattern: (value, params) => {
            if (!value) return true;
            try {
                return new RegExp(params.pattern).test(String(value));
            } catch (e) {
                return true;
            }
        },
        number: (value) => {
            if (!value && value !== 0) return true;
            const normalized = String(value).replace(/\./g, '').replace(',', '.');
            return !isNaN(parseFloat(normalized)) && isFinite(normalized);
        }, 
        // ✅ YENİ: Şifre Tekrar Kontrolü
        match: (value, params, field) => {
            if (!value) return true;
            const targetSelector = params.target;
            const targetField = document.querySelector(targetSelector);
            if (!targetField) return true;
            return value === targetField.value;
        },
        // ✅ YENİ: Tarih Aralığı Kontrolü (Start <= End)
        dateRange: (value, params, field) => {
            if (!value) return true;
            // Bu alan "Bitiş" tarihi ise ve "Başlangıç" tarihi varsa kontrol et
            if (field.id.endsWith('_end')) {
                const startId = field.id.replace('_end', '_start');
                const startField = document.getElementById(startId);
                if (startField && startField.value) {
                    return value >= startField.value;
                }
            }
            return true;
        }
    };

    // ==========================================
    // TÜRKİYE ÖZEL VALİDASYON KURALLARI
    // ==========================================
    const TR_RULES = {
        tckn: (value) => {
            if (!value) return { valid: true };
            const tckn = String(value).replace(/\D/g, '');

            if (tckn.length === 0) return { valid: true };
            if (tckn.length !== 11) return { valid: false, message: formatMessage(MESSAGES.tcknLength, { current: tckn.length }) };
            if (tckn.charAt(0) === '0') return { valid: false, message: MESSAGES.tcknFirstZero };
            if (/^(\d)\1{10}$/.test(tckn)) return { valid: false, message: MESSAGES.tcknAlgorithm };

            const digits = tckn.split('').map(d => parseInt(d, 10));
            
            const oddSum = digits[0] + digits[2] + digits[4] + digits[6] + digits[8];
            const evenSum = digits[1] + digits[3] + digits[5] + digits[7];
            
            const tenthDigit = ((oddSum * 7) - evenSum) % 10;
            const eleventhDigit = (digits.slice(0, 10).reduce((a, b) => a + b, 0)) % 10;

            if (digits[9] !== tenthDigit || digits[10] !== eleventhDigit) {
                return { valid: false, message: MESSAGES.tcknAlgorithm };
            }

            return { valid: true };
        },

        vkn: (value) => {
            if (!value) return { valid: true };
            const vkn = String(value).replace(/\D/g, '');

            if (vkn.length === 0) return { valid: true };
            if (vkn.length !== 10) return { valid: false, message: formatMessage(MESSAGES.vknLength, { current: vkn.length }) };

            const digits = vkn.split('').map(d => parseInt(d, 10));
            let sum = 0;

            for (let i = 0; i < 9; i++) {
                const tmp = (digits[i] + (9 - i)) % 10;
                const result = (tmp * Math.pow(2, 9 - i)) % 9;
                sum += (tmp !== 0 && result === 0) ? 9 : result;
            }

            const lastDigit = sum % 10 === 0 ? 0 : (10 - (sum % 10));

            if (digits[9] !== lastDigit) {
                return { valid: false, message: MESSAGES.vknAlgorithm };
            }

            return { valid: true };
        },

        iban: (value) => {
            if (!value) return { valid: true };
            const iban = String(value).replace(/[\s\-]/g, '').toUpperCase();

            if (iban.length === 0) return { valid: true };
            if (!iban.startsWith('TR')) return { valid: false, message: MESSAGES.ibanPrefix };
            if (iban.length !== 26) return { valid: false, message: formatMessage(MESSAGES.ibanLength, { current: iban.length }) };

            // BigInt ile Modern çözüm (Eski döngüye gerek yok)
            const rearranged = iban.substring(4) + iban.substring(0, 4);
            const numeric = rearranged.replace(/[A-Z]/g, char => char.charCodeAt(0) - 55);

            // BigInt desteği varsa kullan, yoksa hata vermemesi için try-catch (Modern tarayıcılar destekler)
            try {
                if (BigInt(numeric) % 97n !== 1n) {
                    return { valid: false, message: MESSAGES.ibanAlgorithm };
                }
            } catch (e) {
                console.warn("BigInt desteklenmiyor, IBAN kontrolü atlandı.");
            }

            return { valid: true };
        },

        phoneTR: (value) => {
            if (!value) return { valid: true };
            let phone = String(value).replace(/[\s\-\(\)\+\_]/g, '');

            if (phone.startsWith('90')) phone = phone.substring(2);
            if (phone.startsWith('0')) phone = phone.substring(1);

            if (phone.length === 0) return { valid: true };
            if (phone.length !== 10) return { valid: false, message: formatMessage(MESSAGES.phoneTRLength, { current: phone.length }) };
            if (phone.charAt(0) !== '5') return { valid: false, message: MESSAGES.phoneTRPrefix };

            return { valid: true };
        },

        plate: (value) => {
            if (!value) return { valid: true };
            const plate = String(value).replace(/\s/g, '').toUpperCase();

            if (plate.length === 0) return { valid: true };
            if (plate.length < 5 || plate.length > 8) return { valid: false, message: MESSAGES.plate };

            // Basit Regex Kontrolleri
            const plateRegex = /^(0[1-9]|[1-7][0-9]|8[01])[A-Z]{1,3}\d{2,4}$/;
            
            if (!plateRegex.test(plate)) {
                 // Regex başarısızsa önce ili kontrol edelim, il yanlışsa il hatası verelim
                 const cityCode = parseInt(plate.substring(0, 2), 10);
                 if (isNaN(cityCode) || cityCode < 1 || cityCode > 81) {
                     return { valid: false, message: MESSAGES.plateCity };
                 }
                 return { valid: false, message: MESSAGES.plate };
            }

            return { valid: true };
        },

        creditCard: (value) => {
            if (!value) return { valid: true };
            const card = String(value).replace(/[\s\-]/g, '');

            if (card.length === 0) return { valid: true };
            if (card.length < 13 || card.length > 19) return { valid: false, message: formatMessage(MESSAGES.creditCardLength, { current: card.length }) };

            // Luhn Algoritması
            let sum = 0;
            let isEven = false;

            for (let i = card.length - 1; i >= 0; i--) {
                let digit = parseInt(card.charAt(i), 10);
                if (isEven) {
                    digit *= 2;
                    if (digit > 9) digit -= 9;
                }
                sum += digit;
                isEven = !isEven;
            }

            if (sum % 10 !== 0) return { valid: false, message: MESSAGES.creditCardAlgorithm };

            return { valid: true };
        },

        tckn_vkn: (value) => {
        if (!value) return { valid: true };
        const val = String(value).replace(/\D/g, ''); // Sadece rakamlar

        if (val.length === 10) {
            // 10 Haneyse VKN Kontrolü Yap
            return TR_RULES.vkn(val);
        } else if (val.length === 11) {
            // 11 Haneyse TCKN Kontrolü Yap
            return TR_RULES.tckn(val);
        } else {
            return { valid: false, message: '10 veya 11 haneli olmalıdır.' };
        }
        },

        dateTR: (value) => {
            if (!value) return { valid: true };

            // --- SENARYO 1: Native Date Input (YYYY-MM-DD) ---
            // type="date" olan alanlar bu formatı gönderir
            if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
                const parts = value.split('-');
                const year = parseInt(parts[0], 10);
                const month = parseInt(parts[1], 10);
                const day = parseInt(parts[2], 10);

                if (month < 1 || month > 12) return { valid: false, message: MESSAGES.dateInvalid };
                
                const daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
                // Artık yıl kontrolü
                if ((year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0)) daysInMonth[1] = 29;

                if (day < 1 || day > daysInMonth[month - 1]) return { valid: false, message: MESSAGES.dateInvalid };
                
                return { valid: true };
            }

            // --- SENARYO 2: Maskeli Text Input (DD.MM.YYYY) ---
            // FieldType.TARIH bu formatı kullanır
            const dateStr = String(value).replace(/\D/g, '');

            if (dateStr.length === 0) return { valid: true };
            if (dateStr.length !== 8) return { valid: false, message: MESSAGES.date };

            const day = parseInt(dateStr.substring(0, 2), 10);
            const month = parseInt(dateStr.substring(2, 4), 10);
            const year = parseInt(dateStr.substring(4, 8), 10);

            if (month < 1 || month > 12) return { valid: false, message: MESSAGES.dateInvalid };

            const daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
            if ((year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0)) daysInMonth[1] = 29;

            if (day < 1 || day > daysInMonth[month - 1]) return { valid: false, message: MESSAGES.dateInvalid };

            return { valid: true };
        }
        
        // dateTR bitti.

    };

    // ==========================================
    // TİP EŞLEŞTİRMELERİ
    // ==========================================
    const TYPE_CONFIG = {
        'tel': { formatter: 'phoneTR', validator: 'phoneTR' },
        'phone': { formatter: 'phoneTR', validator: 'phoneTR' },
        'telefon': { formatter: 'phoneTR', validator: 'phoneTR' },
        'tckn': { formatter: 'tckn', validator: 'tckn' },
        'tc': { formatter: 'tckn', validator: 'tckn' },
        'vkn': { formatter: 'vkn', validator: 'vkn' },
        'vergi': { formatter: 'vkn', validator: 'vkn' },
        'iban': { formatter: 'iban', validator: 'iban' },
        'plate': { formatter: 'plate', validator: 'plate' },
        'plaka': { formatter: 'plate', validator: 'plate' },
        'credit_card': { formatter: 'creditCard', validator: 'creditCard' },
        'creditcard': { formatter: 'creditCard', validator: 'creditCard' },
        'kredi_karti': { formatter: 'creditCard', validator: 'creditCard' },
        'tarih': { formatter: 'date', validator: 'dateTR' },
        'date': { formatter: 'date', validator: 'dateTR' },
        'currency': { formatter: 'currency', validator: 'number' },
        'para': { formatter: 'currency', validator: 'number' },
        'email': { formatter: null, validator: 'email' },
        'url': { formatter: null, validator: 'url' }, 
        'ip': { formatter: null, validator: 'ip' },
        'auto_number': { formatter: 'uppercase', validator: 'required' },
        'tckn_vkn': { formatter: 'number', validator: 'tckn_vkn' }
    };

    // ==========================================
    // FORM VALIDATOR CLASS (ES6)
    // ==========================================
    class FormValidator {
        constructor(form, options = {}) {
            this.form = form;
            this.options = {
                debounceDelay: 250,
                validateOnInput: true,
                validateOnBlur: true,
                showSuccessState: true,
                formatOnInput: true,
                ...options
            };

            this.timers = {};
            this.init();
        }

        init() {
            
            // Form zaten initialize edilmişse tekrar etme
            if (this.form.dataset.validatorInitialized === 'true') {
                console.warn('⚠️ Bu form zaten validate ediliyor:', this.form);
                return; 
            }
            

            
            // İşaretle ki bir daha çalışmasın
            this.form.dataset.validatorInitialized = 'true';

            this.initDateRangeListeners();
            this.initAgeCalculator();
            this.initPasswordFeatures();
            
            // ============================================================
            // EVENT DELEGATION (Dinamik Alanlar İçin Çözüm)
            // ============================================================
            // Artık tek tek inputlara değil, forma dinleyici ekliyoruz.
            // Böylece sonradan eklenen (Master-Detail) alanlar da otomatik çalışır.

            // 1. INPUT Olayı (Formatlama ve Validasyon)
            this.form.addEventListener('input', (e) => {
                const field = e.target;
                // Sadece form elemanlarıyla ilgilen
                if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(field.tagName)) return;
                if (this.shouldSkip(field)) return;

                const fieldType = this.getFieldType(field);
                const config = TYPE_CONFIG[fieldType];

                // Formatlama (Para birimi, Telefon vb.)
                if (this.options.formatOnInput && config && config.formatter) {
                    this.formatField(field, config.formatter);
                }

                // Validasyon
                if (this.options.validateOnInput) {
                    this.handleInput(field);
                }
            });

            // 2. BLUR Olayı (Odaktan çıkınca kontrol)
            if (this.options.validateOnBlur) {
                this.form.addEventListener('focusout', (e) => {
                    const field = e.target;
                    if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(field.tagName)) return;
                    if (this.shouldSkip(field)) return;

                    this.handleBlur(field);
                });
            }

            // 3. CHANGE Olayı (Select ve Checkboxlar için)
            this.form.addEventListener('change', (e) => {
                const field = e.target;
                if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(field.tagName)) return;
                if (this.shouldSkip(field)) return;

                this.validateField(field, true);
            });

            // 4. KEYDOWN Olayı (Tuş Kısıtlamaları - Sadece rakam girme vb.)
            this.form.addEventListener('keydown', (e) => {
                const field = e.target;
                if (!['INPUT', 'TEXTAREA'].includes(field.tagName)) return;
                if (this.shouldSkip(field)) return;

                const fieldType = this.getFieldType(field);
                const config = TYPE_CONFIG[fieldType];

                if (config && config.formatter) {
                    this.handleKeydown(e, config.formatter);
                }
            });

            // 5. SUBMIT Olayı
            this.form.addEventListener('submit', (e) => {
                // 1. Önce Validasyon Yap
                const isValid = this.validateForm();
                
                if (!isValid) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.scrollToFirstError();
                    if (typeof showWarning === 'function') {
                        showWarning('Lütfen formdaki hataları düzeltin');
                    }
                    return;
                }

                // 2. Validasyon Başarılıysa ve Form AJAX ise
                if (this.form.getAttribute('data-ajax') === 'true') {
                    e.preventDefault(); // Standart gönderimi durdur (JSON ekranını engeller)
                    this.submitAjax();  // AJAX ile gönder
                }
                // Eğer data-ajax="true" değilse standart submit devam eder
            });

       

            const fields = this.form.querySelectorAll('input, select, textarea');

            fields.forEach(field => {
                if (this.shouldSkip(field)) return;

                const fieldType = this.getFieldType(field);
                const config = TYPE_CONFIG[fieldType];

                // Input Event
                field.addEventListener('input', (e) => {
                    if (this.options.formatOnInput && config && config.formatter) {
                        this.formatField(e.target, config.formatter);
                    }
                    if (this.options.validateOnInput) {
                        this.handleInput(e.target);
                    }
                });

                // Blur Event
                if (this.options.validateOnBlur) {
                    field.addEventListener('blur', (e) => this.handleBlur(e.target));
                }

                // Change Event (Dropdowns vs için)
                field.addEventListener('change', (e) => this.validateField(e.target, true));

                // Keydown Event (Tuş kısıtlamaları)
                if (config && config.formatter) {
                    field.addEventListener('keydown', (e) => this.handleKeydown(e, config.formatter));
                }
            });

            // Form Submit Event
            this.form.addEventListener('submit', (e) => {
                const isValid = this.validateForm();
                if (!isValid) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.scrollToFirstError();
                    if (typeof showWarning === 'function') {
                        showWarning('Lütfen formdaki hataları düzeltin');
                    }
                }
            });

            
            console.log(`✅ FormValidator initialized (Event Delegation): ${this.form.id || 'unnamed'}`);
            console.log(`✅ FormValidator initialized: ${this.form.id || this.form.name || 'unnamed'}`);
        }

         // --- YENİ EKLENECEK METOD: AJAX GÖNDERİMİ ---
        submitAjax() {
            const $form = $(this.form);
            const formData = new FormData(this.form);
            const submitBtn = $form.find('[type="submit"]');
            const originalText = submitBtn.html();

            // Butonu kilitle ve spinner göster
            submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> İşleniyor...');

            $.ajax({
                url: $form.attr('action'),
                method: $form.attr('method') || 'POST',
                data: formData,
                processData: false, // Dosya yükleme için gerekli
                contentType: false, // Dosya yükleme için gerekli
                success: function(response) {
                    if (response.success) {
                        // BAŞARILI
                        Swal.fire({
                            title: 'Başarılı!',
                            text: response.message,
                            icon: 'success',
                            confirmButtonText: 'Tamam'
                        }).then((result) => {
                            if (response.redirect) {
                                window.location.href = response.redirect;
                            } else {
                                // Yönlendirme yoksa formu temizle veya sayfayı yenile
                                // window.location.reload(); 
                                // Veya sadece formu resetle:
                                // $form[0].reset(); 
                                // $('.select2-field').val(null).trigger('change');
                                
                                // Çek ekranında listeye dönmek mantıklı olabilir:
                                // window.location.href = "/cek"; 
                            }
                        });
                    } else {
                        // SUNUCU TARAFI MANTIKSAL HATA (Örn: Mükerrer Kayıt)
                        Swal.fire({
                            title: 'İşlem Başarısız',
                            text: response.message,
                            icon: 'error',
                            confirmButtonText: 'Tamam'
                        });
                    }
                },
                error: function(xhr) {
                    // SUNUCU HATASI (500, 404 vb.)
                    let errorMsg = 'Sunucu ile iletişim kurulamadı.';
                    if (xhr.responseJSON && xhr.responseJSON.message) {
                        errorMsg = xhr.responseJSON.message;
                    }
                    
                    Swal.fire({
                        title: 'Hata!',
                        text: errorMsg,
                        icon: 'error',
                        confirmButtonText: 'Tamam'
                    });
                },
                complete: function() {
                    // Butonu eski haline getir
                    submitBtn.prop('disabled', false).html(originalText);
                }
            });
        }

        // --- Ekstra Özellikler ---
        initDateRangeListeners() {
                this.form.querySelectorAll('input[id$="_end"]').forEach(end => {
                    const start = document.getElementById(end.id.replace('_end', '_start'));
                    if (start) start.addEventListener('change', () => this.validate(end));
                });
        }

        initAgeCalculator() {
            const birthFields = this.form.querySelectorAll('input[name="birth_date"], input[name="dogum_tarihi"]');
            const ageField = this.form.querySelector('input[name="age"]');
            if (birthFields.length && ageField) {
                birthFields.forEach(f => f.addEventListener('blur', (e) => {
                    if (e.target.value.length === 10) {
                        const p = e.target.value.split('.');
                        const age = new Date().getFullYear() - parseInt(p[2]);
                        ageField.value = age;
                        this.validate(ageField);
                    }
                }));
            }
        }

       initPasswordFeatures() {
    // 1. Şifre Giriş Olayı
    $('input.password-strength').on('input', function() {
        var $input = $(this);
        var pwd = $input.val();
        var id = this.id;
        
        // --- A) Progress Bar Mantığı (Mevcut Kod) ---
        var score = 0;
        if (pwd.length > 0) score += 10;
        if (pwd.length >= 8) score += 20;
        if (/[A-Z]/.test(pwd)) score += 20;
        if (/[a-z]/.test(pwd)) score += 20;
        if (/[0-9]/.test(pwd)) score += 15;
        if (/[^A-Za-z0-9]/.test(pwd)) score += 15;

        var $bar = $('#' + id + '_strength_bar .progress-bar');
        $bar.css('width', score + '%').removeClass('bg-danger bg-warning bg-success');
        
        if (score < 40) $bar.addClass('bg-danger');
        else if (score < 80) $bar.addClass('bg-warning');
        else $bar.addClass('bg-success');

        // --- B) Kural Listesi (Policy) Güncelleme (YENİ) ---
        var $policyList = $('#' + id + '_policy');
        
        // Data attribute'larından kuralları al
        var minLen = parseInt($input.data('min') || 0);
        var minUpper = parseInt($input.data('upper') || 0);
        var minDigit = parseInt($input.data('digit') || 0);
        var minSpecial = parseInt($input.data('special') || 0);

        // Yardımcı fonksiyon: Liste elemanını güncelle
        function updateRuleState(ruleName, isValid) {
            var $li = $policyList.find('li[data-rule="' + ruleName + '"]');
            var $icon = $li.find('i');
            
            if (isValid) {
                // BAŞARILI: Yeşil renk ve Dolu Tik/Daire
                $li.removeClass('text-danger text-muted').addClass('text-success fw-bold');
                $icon.removeClass('far fa-circle fa-times-circle').addClass('fas fa-check-circle');
            } else {
                // BAŞARISIZ: Kırmızı renk ve Boş/Çarpı Daire
                // Şifre boşsa gri (muted), hatalıysa kırmızı (danger) yapabiliriz. 
                // İsteğinize göre "diğer türde kırmızı" dediğiniz için direkt danger yapıyorum.
                var colorClass = pwd.length === 0 ? 'text-muted' : 'text-danger';
                $li.removeClass('text-success fw-bold text-muted text-danger').addClass(colorClass);
                $icon.removeClass('fas fa-check-circle').addClass('far fa-circle');
            }
        }

        // 1. Uzunluk Kontrolü
        if (minLen > 0) {
            updateRuleState('min', pwd.length >= minLen);
        }

        // 2. Büyük Harf Kontrolü
        if (minUpper > 0) {
            // Regex: En az minUpper kadar büyük harf var mı?
            var upperCount = (pwd.match(/[A-Z]/g) || []).length;
            updateRuleState('upper', upperCount >= minUpper);
        }

        // 3. Rakam Kontrolü
        if (minDigit > 0) {
            var digitCount = (pwd.match(/[0-9]/g) || []).length;
            updateRuleState('digit', digitCount >= minDigit);
        }

        // 4. Özel Karakter Kontrolü
        if (minSpecial > 0) {
            // Harf ve rakam olmayan her şey özel karakterdir
            var specialCount = (pwd.match(/[^A-Za-z0-9]/g) || []).length;
            updateRuleState('special', specialCount >= minSpecial);
        }
    });

    // 2. Şifre Göster/Gizle Butonu
    $('[data-toggle-password]').on('click', function() {
        var inp = $('#' + $(this).data('toggle-password'));
        var type = inp.attr('type') === 'password' ? 'text' : 'password';
        inp.attr('type', type);
        $(this).find('i').toggleClass('fa-eye fa-eye-slash');
    });
}

        getFieldType(field) {
            return (field.getAttribute('data-type') || field.type || 'text').toLowerCase();
        }

        shouldSkip(field) {
            if (field.type === 'hidden' && !field.getAttribute('data-validate')) return true;
            if (['submit', 'button', 'reset'].includes(field.type)) return true;
            return field.disabled;
        }

        formatField(field, formatterName) {
            const formatter = FORMATTERS[formatterName];
            if (!formatter) return;

            const cursorPos = field.selectionStart;
            const oldLength = field.value.length;

            const result = formatter(field.value, cursorPos);

            if (field.value !== result.formatted) {
                field.value = result.formatted;
                
                // Cursor pozisyonunu koru
                const newLength = result.formatted.length;
                let newCursorPos = cursorPos + (newLength - oldLength);
                
                // Cursor negatif veya taşmışsa düzelt
                if (newCursorPos < 0) newCursorPos = 0;
                if (newCursorPos > newLength) newCursorPos = newLength;

                try {
                    field.setSelectionRange(newCursorPos, newCursorPos);
                } catch (e) {
                    // Bazı input tipleri (email, number) selection API desteklemez
                }
            }
        }


        handleKeydown(e, formatterName) {
            const allowedKeys = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Home', 'End', 'Enter'];
            
            // Eğer kontrol tuşlarına basılıyorsa (Ctrl+C, Ctrl+V vb.) izin ver
            if (e.ctrlKey || e.metaKey || e.altKey) return;
            // İzin verilen navigasyon tuşlarıysa izin ver
            if (allowedKeys.includes(e.key)) return;

            // Rakam Gerektirenler
            if (['tckn', 'vkn', 'phoneTR', 'creditCard', 'date'].includes(formatterName)) {
                if (!/^\d$/.test(e.key)) e.preventDefault();
            }

            // Alfanümerik Gerektirenler
            if (['iban', 'plate'].includes(formatterName)) {
                if (!/^[a-zA-Z0-9]$/.test(e.key)) e.preventDefault();
            }
        }

        handleInput(field) {
            const fieldId = field.name || field.id || Math.random().toString();
            if (this.timers[fieldId]) clearTimeout(this.timers[fieldId]);

            this.timers[fieldId] = setTimeout(() => {
                this.validateField(field, false);
            }, this.options.debounceDelay);
        }

        handleBlur(field) {
            const fieldId = field.name || field.id;
            if (this.timers[fieldId]) {
                clearTimeout(this.timers[fieldId]);
                delete this.timers[fieldId];
            }
            this.validateField(field, this.options.showSuccessState);
        }

        validateField(field, showSuccess) {
            const value = this.getFieldValue(field);
            const fieldType = this.getFieldType(field);
            const config = TYPE_CONFIG[fieldType];
            let errorMessage = null;

            // 1. Required Check
            if (field.required && !RULES.required(value)) {
                errorMessage = MESSAGES.required;
            }

            // Boş değerse ve zorunlu değilse, başarılı say ve çık
            if (!errorMessage && !value && value !== 0) {
                this.showValid(field, false);
                return true;
            }

            // 2. Min/Max Length
            if (!errorMessage && field.minLength > 0 && field.minLength < 50000) {
                if (!RULES.minLength(value, { min: field.minLength })) {
                    errorMessage = formatMessage(MESSAGES.minLength, { min: field.minLength, current: String(value).length });
                }
            }
            if (!errorMessage && field.maxLength > 0 && field.maxLength < 50000) {
                if (!RULES.maxLength(value, { max: field.maxLength })) {
                    errorMessage = formatMessage(MESSAGES.maxLength, { max: field.maxLength });
                }
            }

            // 3. Min/Max Value
            if (!errorMessage && field.min) {
                if (!RULES.min(value, { min: field.min })) errorMessage = formatMessage(MESSAGES.min, { min: field.min });
            }
            if (!errorMessage && field.max) {
                if (!RULES.max(value, { max: field.max })) errorMessage = formatMessage(MESSAGES.max, { max: field.max });
            }

            // 4. Pattern
            if (!errorMessage && field.pattern) {
                if (!RULES.pattern(value, { pattern: field.pattern })) errorMessage = field.title || MESSAGES.pattern;
            }

            // 5. Type Validations
            if (!errorMessage && config && config.validator) {
                const validatorName = config.validator;
                if (TR_RULES[validatorName]) {
                    const result = TR_RULES[validatorName](value);
                    if (!result.valid) errorMessage = result.message;
                } else if (RULES[validatorName]) {
                    if (!RULES[validatorName](value)) errorMessage = MESSAGES[validatorName] || MESSAGES.invalid;
                }
            }

            if (errorMessage) {
                this.showInvalid(field, errorMessage);
                return false;
            } else {
                this.showValid(field, showSuccess);
                return true;
            }
        }

        validateForm() {
            const fields = this.form.querySelectorAll('input, select, textarea');
            let isFormValid = true;

            fields.forEach(field => {
                if (this.shouldSkip(field)) return;

                // Gizli koşullu alanları atla (Bootstrap d-none veya display:none)
                const container = field.closest('.conditional-field, [data-conditional]');
                if (container && (container.classList.contains('d-none') || getComputedStyle(container).display === 'none')) {
                    return;
                }

                if (!this.validateField(field, true)) {
                    isFormValid = false;
                }
            });

            return isFormValid;
        }

        getFieldValue(field) {
            const type = field.type ? field.type.toLowerCase() : '';
            if (type === 'checkbox') return field.checked ? (field.value || 'on') : '';
            if (type === 'radio') {
                const checked = this.form.querySelector(`input[name="${field.name}"]:checked`);
                return checked ? checked.value : '';
            }
            if (field.tagName === 'SELECT' && field.multiple) {
                return Array.from(field.selectedOptions).map(opt => opt.value);
            }
            return field.value;
        }

        showValid(field, showSuccess) {
            this.clearStates(field);
            if (showSuccess && field.value) {
                field.classList.add('is-valid');
            }
        }

        // FormValidator class'ının içindeki metodları bu şekilde güncelleyin:

        // ... form-handler.js içindeki showInvalid fonksiyonu ...
        // ==========================================
// GÜNCELLENMİŞ HATA GÖSTERİM FONKSİYONLARI
// ==========================================

showInvalid(field, message) {
    // Önce temizlik
    this.clearStates(field);
    
    // Sınıf ekle
    field.classList.add('is-invalid');
    
    // Select2 ise, çerçevesini kırmızı yap (Görsel geri bildirim için)
    if (field.classList.contains('select2-hidden-accessible')) {
        const wrapper = $(field).next('.select2-container').find('.select2-selection');
        if(wrapper.length) wrapper.addClass('is-invalid border-danger');
    }

    // Mesaj elementini oluştur
    const feedback = document.createElement('div');
    feedback.className = 'invalid-feedback d-block';
    feedback.innerHTML = `<i class="fas fa-exclamation-circle me-1"></i>${message}`;

    // --- Mesajı Nereye Ekleyeceğiz? ---
    
    // 1. Input Group mu? (Para birimi, Telefon vb.)
    const inputGroup = field.closest('.input-group');
    
    // 2. Select2 mi?
    const isSelect2 = field.classList.contains('select2-hidden-accessible');

    if (isSelect2) {
        // Select2 container'ını bul ve sonrasına ekle
        const select2Container = field.nextElementSibling; // Genellikle hemen sonrasındadır
        if (select2Container && select2Container.classList.contains('select2-container')) {
            select2Container.insertAdjacentElement('afterend', feedback);
        } else {
            // Bulamazsa parent'a ekle
            field.parentElement.appendChild(feedback);
        }
    } 
    else if (inputGroup) {
        // Input Group ise grubun sonuna ekle
        inputGroup.insertAdjacentElement('afterend', feedback);
    } 
    else {
        // Standart input
        field.insertAdjacentElement('afterend', feedback);
    }
}

clearStates(field) {
    // 1. Input üzerindeki validation sınıflarını kaldır
    field.classList.remove('is-valid', 'is-invalid');

    // 2. Select2 ise, onun görsel container'ındaki sınıfları da temizlemeliyiz
    if (field.classList.contains('select2-hidden-accessible')) {
        const wrapper = $(field).next('.select2-container').find('.select2-selection');
        if(wrapper.length) {
            wrapper.removeClass('is-valid is-invalid border-danger');
        }
    }

    // 3. Kapsayıcıyı (Container) Geniş Kapsamlı Bul
    // .mb-3, .col-*, .input-group veya .form-group arıyoruz
    let container = field.closest('.mb-3') || field.closest('[class*="col-"]') || field.closest('.form-group');

    // Eğer standart yapı yoksa input-group veya parent'a bak
    if (!container) {
        const inputGroup = field.closest('.input-group');
        container = inputGroup ? inputGroup.parentElement : field.parentElement;
    }

    // 4. Bulunan kapsayıcı içindeki TÜM hata mesajlarını sil (Yığılmayı önler)
    if (container) {
        container.querySelectorAll('.invalid-feedback, .valid-feedback').forEach(el => el.remove());
    }
}

        scrollToFirstError() {
            const firstError = this.form.querySelector('.is-invalid');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => firstError.focus(), 300);
            }
        }
    }

    // ==========================================
    // TOAST BİLDİRİMLERİ
    // ==========================================
    const getOrCreateToastContainer = () => {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        return container;
    };

    const showToast = (message, type = 'info', duration = 4000) => {
        const container = getOrCreateToastContainer();
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-times-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        const bgColors = {
            success: 'bg-success',
            error: 'bg-danger',
            warning: 'bg-warning',
            info: 'bg-info'
        };
        const textColors = {
            success: 'text-white',
            error: 'text-white',
            warning: 'text-dark',
            info: 'text-white'
        };

        const toastId = `toast-${Date.now()}`;
        
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center ${bgColors[type]} ${textColors[type]} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body d-flex align-items-center">
                        <i class="${icons[type]} me-2 fs-5"></i>
                        <span>${message}</span>
                    </div>
                    <button type="button" class="btn-close ${type !== 'warning' ? 'btn-close-white' : ''} me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', toastHtml);
        const toastElement = document.getElementById(toastId);

        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: duration });
            toastElement.addEventListener('hidden.bs.toast', () => toastElement.remove());
            toast.show();
        } else {
            toastElement.classList.add('show');
            toastElement.style.display = 'block';
            setTimeout(() => {
                toastElement.classList.remove('show');
                setTimeout(() => toastElement.remove(), 150);
            }, duration);
        }
    };

    // Global erişimler
    window.showSuccess = (msg, duration) => showToast(msg, 'success', duration);
    window.showError = (msg, duration) => showToast(msg, 'error', duration);
    window.showWarning = (msg, duration) => showToast(msg, 'warning', duration);
    window.showInfo = (msg, duration) => showToast(msg, 'info', duration);
    window.showToast = showToast;

    // ==========================================
    // OTOMATİK BAŞLATMA
    // ==========================================
    const init = () => {
        initFileDropzones();
        initMapPoint();
        initSignaturePad();
        initRichText();
        initBarcode();
        initAutoCalculation();
        initConditionalLogic();
        initDependentSelects();
        initTextTransform();
        initMediaRecorders();
        initPriceRange();
        initRatingFields();
        initDrawingField();
        initCalcFields();
        initMasking();
        initImagePreview();
        initAdvancedColorPicker();
        initSingleSlider();
        initGeolocation(); 
        initMultiField();  
        initDateRange();
        initAutocomplete();
        initSearchAndButtons();
        initModalFixes();
        initializeSelect2();
        initUniqueCheck();
        initAutoNumber();
        initDependentFields();
        initKeyboardActions();
		
        initGlobalFormNavigation();
        
        const forms = document.querySelectorAll('form[data-form-handler]');
        if (forms.length === 0) {
            console.log('ℹ️ data-form-handler attribute\'u olan form bulunamadı.');
            return;
        }

        forms.forEach(form => {
            new FormValidator(form, {
                validateOnInput: form.getAttribute('data-realtime') !== 'false',
                formatOnInput: form.getAttribute('data-format') !== 'false',
                showSuccessState: true,
                debounceDelay: parseInt(form.getAttribute('data-debounce')) || 400
            });
        });

        console.log(`🚀 Form Builder Validation & Formatting System hazır! (${forms.length} form)`);
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // ==========================================
    // GLOBAL ERİŞİM
    // ==========================================
    window.FormValidator = FormValidator;
    window.FormBuilderValidation = {
        FormValidator,
        RULES,
        TR_RULES,
        FORMATTERS,
        MESSAGES,
        TYPE_CONFIG,
        
        init: (formSelector, options) => {
            const form = typeof formSelector === 'string' 
                ? document.querySelector(formSelector) 
                : formSelector;
            if (!form) {
                console.error('Form not found:', formSelector);
                return null;
            }
            return new FormValidator(form, options);
        },
        
        format: (value, type) => {
            const config = TYPE_CONFIG[type.toLowerCase()];
            if (config && config.formatter && FORMATTERS[config.formatter]) {
                return FORMATTERS[config.formatter](value);
            }
            return { formatted: value };
        },
        
        validate: (value, type) => {
            const config = TYPE_CONFIG[type.toLowerCase()];
            if (config && config.validator) {
                if (TR_RULES[config.validator]) {
                    return TR_RULES[config.validator](value);
                }
                if (RULES[config.validator]) {
                    return { valid: RULES[config.validator](value) };
                }
            }
            return { valid: true };
        },
        
        version: '25.52.0'
    };

// ==========================================
// MASTER-DETAIL SATIR EKLEME (HİBRİT MOTOR)
// Hem <template> yapısını hem de satır kopyalamayı destekler.
// ==========================================
/**
 * FORM BUILDER GLOBAL VALIDATION & ACTION LIBRARY
 * Tüm Master-Detail, Hesaplama ve Validasyon işlemleri buradan yönetilir.
 */

// =========================================================
// 1. MASTER-DETAIL SATIR YÖNETİMİ (HİBRİT MOTOR)
// Hem <template> yapısını (Eski Formlar) hem de satır kopyalamayı (Fatura) destekler.
// =========================================================

window.mdAddRow = function(arg) {
    console.log("👉 mdAddRow Çalıştı. Hedef:", arg);

    var $tbody = null;
    var $template = null;
    var mode = 'clone'; // Varsayılan mod: Satır Kopyala (Fatura vb.)

    // ---------------------------------------------------------
    // 1. ADIM: ŞABLON (TEMPLATE) KONTROLÜ (Eski Formlar İçin)
    // ---------------------------------------------------------
    if (typeof arg === 'string') {
        var templateId = 'tpl_' + arg;
        var templateEl = document.getElementById(templateId);
        
        if (templateEl) {
            console.log("✅ Şablon bulundu (" + templateId + "), şablon modu kullanılıyor.");
            mode = 'template';
            
            // Tabloyu bul
            var tableId = 'tbl_' + arg;
            var $table = $('#' + tableId);
            if ($table.length === 0) $table = $('#' + arg);
            if ($table.length === 0) $table = $('table[name="' + arg + '"]');
            
            if ($table.length > 0) {
                $tbody = $table.find('tbody');
                $template = templateEl;
            }
        }
    }

    // ---------------------------------------------------------
    // 2. ADIM: AKILLI ARAMA VE SATIR KOPYALAMA (Fatura İçin)
    // ---------------------------------------------------------
    if (mode === 'clone') {
        var $table = null;
        
        // İsme göre ara
        if (typeof arg === 'string') {
            if ($('#' + arg).length > 0) $table = $('#' + arg);
            else if ($('#table_' + arg).length > 0) $table = $('#table_' + arg);
            else if ($('table[name="' + arg + '"]').length > 0) $table = $('table[name="' + arg + '"]');
        }
        
        // Bulunamadıysa butondan yola çık (Akıllı Arama)
        if ((!$table || $table.length === 0) && (typeof arg === 'object' || window.event)) {
            var el = (typeof arg === 'object') ? arg : window.event.target;
            var $btn = $(el).closest('button');
            if($btn.length === 0) $btn = $(el);

            $table = $btn.parent().find('table'); // Kardeş
            if ($table.length === 0) $table = $btn.closest('.master-detail-container').find('table'); // Ebeveyn
            if ($table.length === 0) $table = $btn.parent().parent().find('table'); // Dede
        }

        if ($table && $table.length > 0) {
            $tbody = $table.find('tbody');
        }
    }

    // HATA KONTROLÜ
    if (!$tbody || $tbody.length === 0) {
        console.error("❌ Hata: Tablo gövdesi (tbody) bulunamadı!");
        alert("İşlem yapılacak tablo bulunamadı.");
        return;
    }

    var $newRow = null;

    // ---------------------------------------------------------
    // 3. ADIM: YENİ SATIR OLUŞTURMA
    // ---------------------------------------------------------
    if (mode === 'template') {
        // A) Şablondan Üret (Boş tablolar için)
        var clone = $template.content.cloneNode(true);
        $newRow = $(clone.querySelector('tr'));
        
        // Benzersiz ID Üret
        var uniqueSuffix = '_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
        $newRow.find('input, select, textarea').each(function() {
            var el = $(this);
            var oid = el.attr('id');
            if (oid) el.attr('id', oid + uniqueSuffix);
        });

    } else {
        // B) Mevcut Satırdan Kopyala (Fatura gibi dolu tablolar için)
        var $firstRow = $tbody.find('tr:first');
        if ($firstRow.length === 0) {
            alert("Tablo boş ve şablon bulunamadı. Lütfen sayfayı yenileyin.");
            return;
        }
        
        $newRow = $firstRow.clone();
        
        // Temizlik (Select2, ID vb.)
        $newRow.find('.select2-container').remove();
        $newRow.find('.select2-hidden-accessible').removeClass('select2-hidden-accessible').removeAttr('data-select2-id').removeAttr('aria-hidden').removeAttr('tabindex');
        
        // Değerleri Sıfırla
        $newRow.find('input, select, textarea').each(function() {
            $(this).removeAttr('id'); // ID çakışmasın
            if ($(this).is(':checkbox') || $(this).is(':radio')) $(this).prop('checked', false);
            else $(this).val('').removeAttr('value');
        });
        
        $newRow.find('select option').removeAttr('data-select2-id');
        $newRow.find('.md-calc-total').text('');
        $newRow.find('.md-calc-total').val('');
    }

    // ---------------------------------------------------------
    // 4. ADIM: EKLEME VE BAŞLATMA
    // ---------------------------------------------------------
   // ... mdAddRow kodlarının başı ...

    // ---------------------------------------------------------
    // 4. ADIM: EKLEME VE BAŞLATMA
    // ---------------------------------------------------------
    $tbody.append($newRow);

    // Eklentileri Başlat
    if ($.fn.select2) {
        $newRow.find('select').each(function() {
            try {
                // Sadece başlat, açma (open) komutu yok.
                $(this).select2({ 
                    width: '100%', 
                    placeholder: 'Seçiniz', 
                    allowClear: true, 
                    language: "tr", 
                    dropdownParent: $(this).parent() 
                });
            } catch (e) {}
        });
    }

    if (typeof Inputmask !== 'undefined') {
        $newRow.find('[data-mask]').inputmask();
    }
    
    // Auto Number Fetch
    $newRow.find('input[data-auto-fetch]').each(function() {
        var url = $(this).data('auto-fetch');
        var input = this;
        fetch(url).then(r => r.json()).then(d => { if(d.code) input.value = d.code; });
    });

    // --- KRİTİK DÜZELTME: Sadece ilk INPUT'a odaklan ---
    // Select2'leri açmadan sadece ilk metin kutusuna veya seçime odaklanır.
    setTimeout(function() {
        var $firstInput = $newRow.find('input:visible, select').filter(function() {
             return $(this).is(':visible') || $(this).hasClass('select2-hidden-accessible');
        }).not('[readonly], [disabled]').first();

        if ($firstInput.length) {
            if ($firstInput.hasClass('select2-hidden-accessible')) {
                $firstInput.select2('open'); // Sadece İLK hücre Select2 ise aç
            } else {
                $firstInput.focus();
            }
        }
    }, 100);
// ---------------------------------------------------------
    // 4. ADIM: EKLEME VE BAŞLATMA
    // ---------------------------------------------------------
    $tbody.append($newRow);

    // Eklentileri Başlat (Select2, Mask vb.)
    
    // Select2 için özel kod yazmak yerine, yukarıdaki akıllı fonksiyonu çağırıyoruz.
    // Böylece AJAX özelliği yeni satıra da otomatik gelir.
    if ($.fn.select2) {
        // Sadece yeni satırdaki select'leri bul ve başlat
        initializeSelect2($newRow);
    }

    if (typeof Inputmask !== 'undefined') {
        $newRow.find('[data-mask]').inputmask();
    }
    
    // Auto Number Fetch
    $newRow.find('input[data-auto-fetch]').each(function() {
        var url = $(this).data('auto-fetch');
        var input = this;
        fetch(url).then(r => r.json()).then(d => { if(d.code) input.value = d.code; });
    });

    // Odaklanma (Focus)
    setTimeout(function() {
        var $firstInput = $newRow.find('input:visible, select').filter(function() {
             return $(this).is(':visible') || $(this).hasClass('select2-hidden-accessible');
        }).not('[readonly], [disabled]').first();

        if ($firstInput.length) {
            if ($firstInput.hasClass('select2-hidden-accessible')) {
                $firstInput.select2('focus'); 
            } else {
                $firstInput.focus();
            }
        }
    }, 100);
    
};

// Satır Silme Fonksiyonu
window.mdRemoveRow = function(btn) {
    var $row = $(btn).closest('tr');
    var $tbody = $row.parent();
    
    if ($tbody.find('tr').length <= 1) {
        $row.find('input').val('').trigger('input');
        $row.find('select').val(null).trigger('change');
        $row.find('.md-calc-total').text('');
        $row.find('.md-calc-total').val('');
    } else {
        $row.remove();
    }
    if (typeof window.mdCalcTotal === 'function') window.mdCalcTotal();
};


// =========================================================
// 2. OTOMATİK HESAPLAMA MOTORU (Miktar * Fiyat - İskonto + KDV)
// =========================================================

// A) Genel Toplam Hesaplama
// Genel Toplam Fonksiyonunu da data-calc destekli yapalım
window.mdCalcTotal = function() {
    var grandTotal = 0;
    // Hem class hem data-calc olanları topla
    $('.md-calc-total, [data-calc="total"]').each(function() {
        var rawVal = $(this).is('input') ? $(this).val() : $(this).text();
        if(rawVal) {
            var val = parseFloat(rawVal.toString().replace(/\./g, '').replace(',', '.') || 0);
            grandTotal += val;
        }
    });

    var $display = $('#md_grand_total');
    if ($display.length) {
        var formatted = grandTotal.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if ($display.is('input')) $display.val(formatted);
        else $display.text(formatted + ' ₺');
    }
};

// B) Satır Bazlı Hesaplama (İSKONTO VE KDV DAHİL)
// B) Satır Bazlı Hesaplama (DATA ATTRIBUTE VERSİYONU)
// Hem eski class yapısını hem yeni data yapısını destekler
$(document).on('input change keyup', 
    '.md-calc-qty, .md-calc-price, .md-calc-tax, .md-calc-discount, [data-calc]', 
    function() {
    
    var $row = $(this).closest('tr');
    
    // Seçiciler: Önce data attribute ara, bulamazsan class ara
    var $qtyInput = $row.find('[data-calc="qty"]').length ? $row.find('[data-calc="qty"]') : $row.find('.md-calc-qty');
    var $priceInput = $row.find('[data-calc="price"]').length ? $row.find('[data-calc="price"]') : $row.find('.md-calc-price');
    var $discountInput = $row.find('[data-calc="discount"]').length ? $row.find('[data-calc="discount"]') : $row.find('.md-calc-discount');
    var $taxInput = $row.find('[data-calc="tax"]').length ? $row.find('[data-calc="tax"]') : $row.find('.md-calc-tax');
    var $totalInput = $row.find('[data-calc="total"]').length ? $row.find('[data-calc="total"]') : $row.find('.md-calc-total');

    if ($qtyInput.length === 0 || $priceInput.length === 0) return;

    function safeParse(val) {
        if (!val) return 0;
        val = val.toString();
        if (val.indexOf(',') > -1) val = val.replace(/\./g, '').replace(',', '.');
        return parseFloat(val) || 0;
    }

    var qty = safeParse($qtyInput.val());
    var price = safeParse($priceInput.val());
    var discountRate = safeParse($discountInput.val());
    var taxRate = safeParse($taxInput.val());
    
    // Hesapla: (Miktar * Fiyat) - İskonto + KDV
    var grossTotal = qty * price;
    var discountAmount = grossTotal * (discountRate / 100);
    var netTotal = grossTotal - discountAmount;
    var taxAmount = netTotal * (taxRate / 100);
    var total = netTotal + taxAmount;

    // Sonucu Yaz
    var formattedTotal = total.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    
    if ($totalInput.is('input')) $totalInput.val(formattedTotal);
    else $totalInput.text(formattedTotal); 

    window.mdCalcTotal();
});


// =========================================================
// 3. YARDIMCI FONKSİYONLAR (KİLİT vb.)
// =========================================================

window.toggleLockGeneric = function(inputId) {
    var inp = document.getElementById(inputId);
    var icon = document.getElementById(inputId + '_lock_icon');
    if (!inp) return;

    if (inp.hasAttribute('readonly')) {
        inp.removeAttribute('readonly');
        inp.style.backgroundColor = '#ffffff';
        inp.style.cursor = 'text';
        inp.focus();
        if(icon) {
            icon.classList.remove('bi-lock-fill');
            icon.classList.add('bi-unlock-fill');
            icon.parentElement.classList.remove('btn-warning');
            icon.parentElement.classList.add('btn-outline-danger');
        }
    } else {
        inp.setAttribute('readonly', 'true');
        inp.style.backgroundColor = '#e9ecef';
        inp.style.cursor = 'not-allowed';
        if(icon) {
            icon.classList.remove('bi-unlock-fill');
            icon.classList.add('bi-lock-fill');
            icon.parentElement.classList.remove('btn-outline-danger');
            icon.parentElement.classList.add('btn-warning');
        }
    }
};




// YARDIMCI: Eklentileri Başlatma
function initRowPlugins($row) {
    // 1. Select2
    if ($.fn.select2) {
        $row.find('select').each(function() {
            try {
                $(this).select2({
                    width: '100%',
                    placeholder: 'Seçiniz',
                    allowClear: true,
                    language: "tr",
                    dropdownParent: $(this).parent()
                });
            } catch (e) {}
        });
    }

    // 2. Inputmask (Varsa)
    if (typeof Inputmask !== 'undefined') {
        $row.find('[data-mask]').inputmask();
    }
    
    // 3. Auto Number Fetch (Varsa - Eski formlar için)
    $row.find('input[data-auto-fetch]').each(function() {
        var url = $(this).data('auto-fetch');
        var input = this;
        fetch(url).then(r => r.json()).then(d => { if(d.code) input.value = d.code; });
    });
}




    // AUTO_NUMBER = "auto_number" # <-- YENİ EKLENEN için
    document.addEventListener("DOMContentLoaded", function() {
    // Otomatik Numara Getirici
    const autoFields = document.querySelectorAll('input[data-auto-fetch]');
    
    autoFields.forEach(function(input) {
        const url = input.getAttribute('data-auto-fetch');
        const spinnerId = input.id + "_spinner";
        const spinner = document.getElementById(spinnerId);

        // Eğer input doluysa (Edit modu gibi) tekrar çekme (Opsiyonel güvenlik)
        if (input.value.trim() !== "") return;

        // Spinner göster
        if(spinner) spinner.style.display = "block";

        fetch(url)
            .then(response => {
                if (!response.ok) throw new Error("API Hatası");
                return response.json();
            })
            .then(data => {
                // API'den { "code": "SIP-2025-001" } gibi bir JSON bekliyoruz
                // Esneklik: 'code', 'next_code', 'value' veya 'id' anahtarlarını dener.
                const val = data.code || data.next_code || data.value || data.id;
                
                if (val) {
                    input.value = val;
                    // Inputun yanıp sönmesi efekti (Görsel geri bildirim)
                    input.style.transition = "background-color 0.5s";
                    input.style.backgroundColor = "#d4edda"; // Yeşilimsi
                    setTimeout(() => {
                        input.style.backgroundColor = "#e9ecef"; // Eski gri
                    }, 1000);
                }
            })
            .catch(err => {
                console.error("Otomatik numara alınamadı:", err);
                input.placeholder = "Numara alınamadı!";
            })
            .finally(() => {
                if(spinner) spinner.style.display = "none";
            });
    });
});

// ==========================================================
// MASTER-DETAIL OTOMATİK HESAPLAMA MOTORU (Global)
// ==========================================================
document.addEventListener('input', function(e) {
    const target = e.target;
    
    // Sadece miktar veya fiyat alanlarında değişiklik olursa çalış
    if (target.name && (target.name.endsWith('_miktar[]') || target.name.endsWith('_birim_fiyat[]'))) {
        
        // Değişikliğin yapıldığı satırı (TR) bul
        const row = target.closest('tr');
        if (!row) return;

        // O satırdaki ilgili diğer inputları bul
        // (İsimlerinin sonu _miktar[], _birim_fiyat[], _tutar[] ile bitenleri yakalar)
        const miktarInput = row.querySelector('input[name$="_miktar[]"]');
        const fiyatInput = row.querySelector('input[name$="_birim_fiyat[]"]');
        const tutarInput = row.querySelector('input[name$="_tutar[]"]');

        if (miktarInput && fiyatInput && tutarInput) {
            // Değerleri Sayıya Çevir (TR formatı: 1.250,50 -> 1250.50)
            let miktar = parseLocaleNumber(miktarInput.value);
            let fiyat = parseLocaleNumber(fiyatInput.value);

            // Hesapla
            let tutar = miktar * fiyat;

            // Tutarı TR formatında yaz (1.250,50)
            // Sadece gösterim içindir, backend temizler.
            tutarInput.value = tutar.toLocaleString('tr-TR', {
                minimumFractionDigits: 2, 
                maximumFractionDigits: 2
            });
        }
    }
});

// Yardımcı: TR Para Formatını JS Float'a Çevirir
function parseLocaleNumber(stringNumber) {
    if (!stringNumber) return 0;
    // Noktaları sil (binlik ayracı), virgülü noktaya çevir (ondalık)
    var clean = stringNumber.toString().replace(/\./g, '').replace(',', '.');
    return parseFloat(clean) || 0;
}

    console.log('✅ Form Builder Validation & Formatting System v1.2 yüklendi.');

})();