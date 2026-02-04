var StokFisiGrid = {
    rowCount: 0,
    
    init: function() {
        var self = this;
        
        // 1. İşlem Türüne Göre Hedef Depo'yu Gizle/Göster
        $('select[name="fis_turu"]').on('change', function() {
            var tur = $(this).val();
            var targetDiv = $('select[name="giris_depo_id"]').closest('.mb-3');
            
            if (tur === 'transfer') {
                targetDiv.slideDown();
                // Transfer ise Çıkış Deposu zorunlu "Kaynak", Giriş "Hedef" olur
                $('label[for="cikis_depo_id"]').text('Kaynak Depo (Çıkış)');
            } else if (tur === 'sayim_fazla' || tur === 'devir' || tur === 'uretim') {
                targetDiv.slideUp();
                $('select[name="giris_depo_id"]').val('').trigger('change');
                // Giriş işlemi olduğu için çıkış deposu mantıken "Giriş Yapılacak Depo" olur
                $('label[for="cikis_depo_id"]').text('İşlem Yapılacak Depo'); 
            } else {
                // Fire, Sayım Eksiği (Çıkış İşlemleri)
                targetDiv.slideUp();
                $('select[name="giris_depo_id"]').val('').trigger('change');
                $('label[for="cikis_depo_id"]').text('Stok Düşülecek Depo');
            }
        });
        
        // Sayfa ilk açıldığında tetikle
        $('select[name="fis_turu"]').trigger('change');

        // 2. Submit Kontrolü
        $('form[name="stok_fisi_form"]').on('submit', function(e) {
            if($('#fisBody tr').length === 0) {
                Swal.fire('Uyarı', 'En az bir stok ekleyiniz.', 'warning');
                e.preventDefault();
                return false;
            }
            
            var detaylar = [];
            $('#fisBody tr').each(function() {
                var row = $(this);
                var stokId = row.find('.stok-select').val();
                if(stokId) {
                    detaylar.push({
                        stok_id: stokId,
                        miktar: parseFloat(row.find('.miktar').val()) || 0,
                        aciklama: row.find('.aciklama').val()
                    });
                }
            });

            if ($('input[name="fis_detaylari"]').length === 0) {
                $('<input>').attr({type: 'hidden', name: 'fis_detaylari', value: JSON.stringify(detaylar)}).appendTo(this);
            } else {
                $('input[name="fis_detaylari"]').val(JSON.stringify(detaylar));
            }
        });

        // 3. Veri Yükleme
        var existingData = $('#existing_fis_data').val();
        if (existingData && existingData !== "[]") {
            try {
                JSON.parse(existingData).forEach(item => self.satirEkle(item));
            } catch(e) {}
        } else {
            this.satirEkle();
        }
    },

    satirEkle: function(item = null) {
        this.rowCount++;
        var id = this.rowCount;
        var options = $('#stokTemplate').html();
        
        var miktar = item ? item.miktar : 1;
        var aciklama = item ? item.aciklama : '';
        
        var tr = `
        <tr id="row_${id}">
            <td><select class="form-select form-select-sm stok-select">${options}</select></td>
            <td><input type="number" class="form-control form-control-sm miktar text-end" value="${miktar}" step="any"></td>
            <td><input type="text" class="form-control form-control-sm aciklama" value="${aciklama}" placeholder="Satır açıklaması..."></td>
            <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="$('#row_${id}').remove()"><i class="bi bi-trash"></i></button></td>
        </tr>`;
        
        $('#fisBody').append(tr);
        
        if (item) $(`#row_${id} .stok-select`).val(item.stok_id);
        
        if($.fn.select2) {
            $(`#row_${id} .stok-select`).select2({theme: 'bootstrap-5', width: '100%'});
        }
    }
};

$(document).ready(function() {
    StokFisiGrid.init();
});