/**
 * Fatura Modülü - Frontend Mantığı
 * Satır ekleme, hesaplama, validasyon ve veri paketleme işlemlerini yönetir.
 */

var FaturaGrid = {
    rowCount: 0,
    
    // Başlangıç Fonksiyonu
    init: function() {
        var self = this;

        // 1. FORM SUBMIT KONTROLÜ
        $('form[name="fatura_form"]').on('submit', function(e) {
            // Validasyon: En az 1 satır olmalı
            if($('#faturaBody tr').length === 0) {
                if(typeof Swal !== 'undefined') {
                    Swal.fire('Hata', 'Lütfen en az bir ürün/hizmet ekleyiniz.', 'warning');
                } else {
                    alert('Lütfen en az bir ürün/hizmet ekleyiniz.');
                }
                e.preventDefault();
                return false;
            }

            // Verileri JSON formatına çevir
            var detaylar = [];
            $('#faturaBody tr').each(function() {
                var row = $(this);
                var stokId = row.find('.stok-select').val();
                
                // Sadece ürün seçili satırları al
                if(stokId) {
                    detaylar.push({
                        stok_id: stokId,
                        miktar: self.parseMoney(row.find('.miktar').val()),
                        birim_fiyat: self.parseMoney(row.find('.fiyat').val()),
                        iskonto_orani: self.parseMoney(row.find('.iskonto').val()),
                        kdv_orani: self.parseMoney(row.find('.kdv').val())
                    });
                }
            });

            // JSON verisini gizli inputa yaz
            // Eğer input formda yoksa (ilk yüklemede) oluştur, varsa güncelle
            if ($('input[name="fatura_detaylari"]').length === 0) {
                $('<input>').attr({
                    type: 'hidden',
                    name: 'fatura_detaylari',
                    value: JSON.stringify(detaylar)
                }).appendTo(this);
            } else {
                $('input[name="fatura_detaylari"]').val(JSON.stringify(detaylar));
            }
        });

        // 2. DÜZENLEME MODU KONTROLÜ (Veri Yükleme)
        // forms.py içinde oluşturduğumuz gizli alandan veriyi oku
        var existingData = $('#existing_fatura_data').val();
        
        if (existingData && existingData !== "[]" && existingData !== "") {
            try {
                var items = JSON.parse(existingData);
                if (items.length > 0) {
                    // Mevcut kalemleri döngüyle ekle
                    items.forEach(function(item) {
                        self.satirEkle_Dolu(item);
                    });
                } else {
                    // Veri boşsa boş satır aç
                    this.satirEkle();
                }
            } catch (e) {
                console.error("JSON Parse Hatası:", e);
                this.satirEkle();
            }
        } else {
            // Yeni faturaysa bir tane boş satır ekle
            this.satirEkle();
        }
    },

    // Yardımcı: TR Para Formatını (1.000,50) Float'a (1000.50) çevirir
    parseMoney: function(value) {
        if (!value) return 0;
        if (typeof value === 'number') return value;
        
        // Önce string yap
        var valStr = value.toString();
        
        // Noktaları (binlik) temizle
        valStr = valStr.replace(/\./g, '');
        
        // Virgülü (ondalık) noktaya çevir
        valStr = valStr.replace(',', '.');
        
        return parseFloat(valStr) || 0;
    },

    // BOŞ SATIR EKLEME
    satirEkle: function() {
        this.rowCount++;
        var id = this.rowCount;
        
        // Şablondaki stok listesini al
        var options = $('#stokListesiTemplate').html();
        
        var tr = `
        <tr id="row_${id}">
            <td>
                <select class="form-select form-select-sm stok-select" onchange="FaturaGrid.stokSecildi(${id})">
                    ${options}
                </select>
            </td>
            <td>
                <input type="number" class="form-control form-control-sm miktar text-end" value="1" min="0.01" step="any" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="number" class="form-control form-control-sm fiyat text-end" value="0" min="0" step="any" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="number" class="form-control form-control-sm iskonto text-end" value="0" min="0" max="100" step="any" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="number" class="form-control form-control-sm kdv text-end" value="20" min="0" max="100" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="text" class="form-control form-control-sm satir-toplam text-end fw-bold" value="0.00" readonly>
            </td>
            <td class="text-center">
                <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="FaturaGrid.satirSil(${id})">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>`;
        
        $('#faturaBody').append(tr);
        
        // Select2 Eklentisini Çalıştır (Varsa)
        if($.fn.select2) {
            $(`#row_${id} .stok-select`).select2({
                theme: 'bootstrap-5',
                width: '100%',
                placeholder: 'Ürün Seçiniz',
                allowClear: true
            });
        }
    },

    // DOLU SATIR EKLEME (Düzenleme Modu İçin)
    satirEkle_Dolu: function(item) {
        this.rowCount++;
        var id = this.rowCount;
        var options = $('#stokListesiTemplate').html();
        
        var tr = `
        <tr id="row_${id}">
            <td>
                <select class="form-select form-select-sm stok-select" onchange="FaturaGrid.stokSecildi(${id})">
                    ${options}
                </select>
            </td>
            <td>
                <input type="number" class="form-control form-control-sm miktar text-end" value="${item.miktar}" min="0.01" step="any" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="number" class="form-control form-control-sm fiyat text-end" value="${item.birim_fiyat}" min="0" step="any" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="number" class="form-control form-control-sm iskonto text-end" value="${item.iskonto_orani}" min="0" max="100" step="any" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="number" class="form-control form-control-sm kdv text-end" value="${item.kdv_orani}" min="0" max="100" oninput="FaturaGrid.hesapla(${id})">
            </td>
            <td>
                <input type="text" class="form-control form-control-sm satir-toplam text-end fw-bold" value="0.00" readonly>
            </td>
            <td class="text-center">
                <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="FaturaGrid.satirSil(${id})">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>`;
        
        $('#faturaBody').append(tr);
        
        // Değerleri Seç
        var $select = $(`#row_${id} .stok-select`);
        $select.val(item.stok_id);

        // Select2 Başlat
        if($.fn.select2) {
            $select.select2({
                theme: 'bootstrap-5', width: '100%', placeholder: 'Ürün Seçiniz'
            });
        }
        
        // Satırı Hesaplat (Toplamları güncellemek için)
        this.hesapla(id);
    },

    // SATIR SİLME
    satirSil: function(id) {
        $(`#row_${id}`).remove();
        this.genelToplamHesapla();
    },

    // STOK SEÇİLDİĞİNDE FİYAT VE KDV GETİRME
    stokSecildi: function(id) {
        var select = $(`#row_${id} .stok-select`).find(':selected');
        
        // Data attribute'lardan veriyi oku (forms.py'da tanımlamıştık)
        var fiyat = parseFloat(select.data('fiyat')) || 0;
        var kdv = parseFloat(select.data('kdv')) || 20;
        
        // Inputları güncelle
        $(`#row_${id} .fiyat`).val(fiyat);
        $(`#row_${id} .kdv`).val(kdv);
        
        // Hesaplamayı tetikle
        this.hesapla(id);
    },

    // TEK SATIR HESAPLAMA
    hesapla: function(id) {
        var row = $(`#row_${id}`);
        
        var miktar = this.parseMoney(row.find('.miktar').val());
        var fiyat = this.parseMoney(row.find('.fiyat').val());
        var iskontoOrani = this.parseMoney(row.find('.iskonto').val());
        var kdvOrani = this.parseMoney(row.find('.kdv').val());
        
        // 1. Brüt Tutar (Miktar x Fiyat)
        var brutTutar = miktar * fiyat;
        
        // 2. İskonto Tutarı
        var iskontoTutari = brutTutar * (iskontoOrani / 100);
        
        // 3. Net Tutar (KDV Matrahı)
        var netTutar = brutTutar - iskontoTutari;
        
        // 4. KDV Tutarı
        var kdvTutari = netTutar * (kdvOrani / 100);
        
        // 5. Satır Genel Toplamı
        var satirToplami = netTutar + kdvTutari;
        
        // Ekrana Yaz (2 hane)
        row.find('.satir-toplam').val(satirToplami.toFixed(2));
        
        // Data attribute olarak ara değerleri sakla (Genel toplam hesabı için lazım)
        row.attr('data-brut-tutar', brutTutar);
        row.attr('data-iskonto-tutar', iskontoTutari);
        row.attr('data-kdv-tutar', kdvTutari);
        row.attr('data-net-tutar', netTutar);
        
        // Genel toplamları güncelle
        this.genelToplamHesapla();
    },

    // DİP TOPLAM HESAPLAMA
    genelToplamHesapla: function() {
        var toplamAra = 0;      // İskontosuz Brüt
        var toplamIskonto = 0;
        var toplamKDV = 0;
        var genelToplam = 0;

        $('#faturaBody tr').each(function() {
            var row = $(this);
            
            // Satır üzerindeki hesaplanmış değerleri al
            var rowBrut = parseFloat(row.attr('data-brut-tutar')) || 0;
            var rowIskonto = parseFloat(row.attr('data-iskonto-tutar')) || 0;
            var rowKdv = parseFloat(row.attr('data-kdv-tutar')) || 0;
            
            toplamAra += rowBrut;
            toplamIskonto += rowIskonto;
            toplamKDV += rowKdv;
        });
        
        // Genel Toplam Formülü: (Brüt - İskonto) + KDV
        genelToplam = (toplamAra - toplamIskonto) + toplamKDV;

        // UI Güncelle (Footer ID'leri forms.py ile uyumlu)
        $('#lblAraToplam').text(toplamAra.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
        $('#lblIskontoToplam').text(toplamIskonto.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
        $('#lblKdvToplam').text(toplamKDV.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
        $('#lblGenelToplam').text(genelToplam.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
    }
};

// Sayfa Yüklendiğinde Başlat
$(document).ready(function() {
    FaturaGrid.init();
}); 