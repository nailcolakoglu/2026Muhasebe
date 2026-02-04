/*
 * DataGrid Logic - Client-Side Script
 * - Sıralama, Gruplama, Filtreleme
 * - Özet Bilgiler (Summary)
 * - Akıllı Silme ve AJAX İşlemleri (URL Otomatik Tamamlama Dahil)
 */

(function(window, $) {
    'use strict';

    // ==================== YARDIMCI FONKSİYONLAR ====================

    function debugOutput(message) {
        if (window.console && window.console.log) {
            console.log('[DATA-GRID] ' + message);
        }
    }

    function saveGroupingState(gridName, groups) {
        try {
            localStorage.setItem('dxGridGroupState_' + gridName, JSON.stringify(groups));
        } catch (e) { console.error("LocalStorage Hatası:", e); }
    }

    function loadGroupingState(gridName) {
        try {
            var state = localStorage.getItem('dxGridGroupState_' + gridName);
            return state ? JSON.parse(state) : [];
        } catch (e) { return []; }
    }

    function parseDate(dateStr) {
        // DD.MM.YYYY veya YYYY-MM-DD algıla
        if (!dateStr) return null;
        var parts = dateStr.split(/[.\/\-]/);
        if (parts.length === 3) {
            // YYYY-MM-DD
            if (parts[0].length === 4) return new Date(parts[0], parts[1] - 1, parts[2]);
            // DD.MM.YYYY
            if (parts[2].length === 4) return new Date(parts[2], parts[1] - 1, parts[0]);
        }
        return null;
    }

    // ==================== 1. GRUPLAMA (GROUPING) ====================
    function initGrouping() {
        $('.dx-grouping-enabled').each(function() {
            var $gridCard = $(this);
            var gridName = $gridCard.attr('id').replace('dx-grid-card-', '');
            var $groupArea = $('#dx-group-area-' + gridName);
            var $grid = $gridCard.find('#dx-grid-' + gridName);
            
            if ($gridCard.data('grouping-init')) return;
            $gridCard.data('grouping-init', true);
            
            var $headers = $grid.find('th.dx-sortable');
            var $tbody = $grid.find('tbody');
            
            if (!$grid.data('original-tbody-html')) {
                $grid.data('original-tbody-html', $tbody.html());
            }
            
            var activeGroups = loadGroupingState(gridName); 
            $headers.attr('draggable', 'true').css('cursor', 'grab');

            function toggleGroupDirection(fieldName) {
                var groupIndex = activeGroups.findIndex(g => g.field === fieldName);
                if (groupIndex !== -1) {
                    var currentDir = activeGroups[groupIndex].direction || 'asc';
                    activeGroups[groupIndex].direction = currentDir === 'asc' ? 'desc' : 'asc';
                    saveGroupingState(gridName, activeGroups); 
                    updateGroupAreaMessage();
                    renderGroupedData();
                }
            }

            function removeGroup(fieldName) {
                activeGroups = activeGroups.filter(g => g.field !== fieldName);
                saveGroupingState(gridName, activeGroups);
                updateGroupAreaMessage();
                renderGroupedData();
            }
            
            function clearAllGroups() {
                activeGroups = [];
                saveGroupingState(gridName, activeGroups);
                updateGroupAreaMessage();
                renderGroupedData();
            }
            
            function updateGroupAreaMessage() {
                if (activeGroups.length === 0) {
                    $groupArea.html('Gruplamak istediğiniz sütun başlığını buraya sürükleyip bırakın.').removeClass('active');
                    $headers.show(); 
                } else {
                    $groupArea.addClass('active').empty();
                    var $clearBtn = $('<button class="btn btn-sm btn-outline-danger ms-2 float-end"><i class="fas fa-times-circle"></i></button>').on('click', clearAllGroups);
                    $groupArea.append($clearBtn);
                    
                    activeGroups.forEach(function(group) {
                        var $header = $grid.find('th.dx-sortable[data-field="' + group.field + '"]');
                        if ($header.length) $header.hide(); 

                        var dirIcon = group.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down';
                        var $tag = $('<span class="badge bg-secondary me-2 dx-group-tag" data-field="' + group.field + '"><i class="fas fa-grip-vertical me-1"></i> ' + group.label + '</span>');
                        
                        var $dirToggle = $(`<i class="fas ${dirIcon} ms-2 dx-group-dir-toggle" style="cursor: pointer;"></i>`).on('click', function(e) { e.stopPropagation(); toggleGroupDirection(group.field); });
                        var $removeBtn = $('<i class="fas fa-times-circle ms-1 dx-group-remove" style="cursor: pointer;"></i>').on('click', function(e) { e.stopPropagation(); removeGroup(group.field); });
                        
                        $tag.append($dirToggle).append($removeBtn);
                        $groupArea.append($tag);
                    });

                    $headers.filter(function() { return !activeGroups.some(g => g.field === $(this).data('field')); }).show();
                }
            }

            $headers.off('dragstart.dxGroup dragend.dxGroup').on('dragstart.dxGroup', function(e) {
                e.originalEvent.dataTransfer.setData('text/plain', $(this).data('field'));
                e.originalEvent.dataTransfer.setData('text/label', $(this).text().trim());
                $(this).addClass('dragging').css('opacity', '0.5');
            }).on('dragend.dxGroup', function() {
                $(this).removeClass('dragging').css('opacity', '');
            });

            $groupArea.off('dragover.dxGroup dragleave.dxGroup drop.dxGroup').on('dragover.dxGroup', function(e) {
                e.preventDefault();
                $(this).addClass('border-primary').css('background-color', '#e3f2fd');
            }).on('dragleave.dxGroup', function() {
                $(this).removeClass('border-primary').css('background-color', '');
            }).on('drop.dxGroup', function(e) {
                e.preventDefault();
                $(this).removeClass('border-primary').css('background-color', '');
                var fieldName = e.originalEvent.dataTransfer.getData('text/plain');
                var fieldLabel = e.originalEvent.dataTransfer.getData('text/label');
                
                if (fieldName && !activeGroups.some(g => g.field === fieldName)) {
                    activeGroups.push({ field: fieldName, label: fieldLabel, direction: 'asc' });
                    saveGroupingState(gridName, activeGroups);
                    updateGroupAreaMessage();
                    renderGroupedData();
                }
            });
            
            function renderGroupedData() {
                if (activeGroups.length === 0) {
                    var originalHtml = $grid.data('original-tbody-html');
                    if (originalHtml) $tbody.empty().html(originalHtml);
                    $headers.show();
                    return;
                }

                var originalHtml = $grid.data('original-tbody-html');
                var $originalRows = $('<div>').html(originalHtml).find('tr').get();
                var visibleFields = $headers.map(function() { return $(this).data('field'); }).get();
                var dataFieldIndexes = {}; 
                $headers.each(function(index) { dataFieldIndexes[$(this).data('field')] = index; });
                
                var allData = [];
                $($originalRows).each(function() {
                    var $cells = $(this).find('td');
                    if ($cells.length === 0) return;
                    var rowData = { element: this };
                    visibleFields.forEach(function(field, index) { rowData[field] = $cells.eq(index).text().trim(); });
                    allData.push(rowData);
                });
                
                allData.sort(function(a, b) {
                    for (var i = 0; i < activeGroups.length; i++) {
                        var group = activeGroups[i];
                        var dir = group.direction === 'desc' ? -1 : 1;
                        var valA = a[group.field], valB = b[group.field];
                        var isNum = !isNaN(parseFloat(valA)) && !isNaN(parseFloat(valB));
                        if (isNum) {
                            if (parseFloat(valA) < parseFloat(valB)) return -1 * dir;
                            if (parseFloat(valA) > parseFloat(valB)) return 1 * dir;
                        } else {
                            var cmp = new Intl.Collator('tr-TR').compare(valA, valB);
                            if (cmp !== 0) return cmp * dir;
                        }
                    }
                    return 0;
                });
                
                $tbody.empty();
                var lastGroupValue = {};
                
                allData.forEach(function(data) {
                    var $dataRow = $(data.element).clone();
                    $dataRow.find('td.dx-group-indent, td.dx-grouped-data').remove(); 
                    
                    activeGroups.forEach(function(group, groupIndex) {
                        var currentValue = data[group.field];
                        if (currentValue !== lastGroupValue[group.field] || (groupIndex > 0 && data[activeGroups[groupIndex-1].field] !== lastGroupValue[activeGroups[groupIndex-1].field])) {
                            lastGroupValue[group.field] = currentValue;
                            for (var i = groupIndex + 1; i < activeGroups.length; i++) lastGroupValue[activeGroups[i].field] = undefined;

                            var $groupRow = $('<tr></tr>').addClass('dx-group-row bg-light');
                            for (var i = 0; i < groupIndex; i++) $groupRow.append('<td class="dx-group-indent"></td>');
                            
                            var colspan = $grid.find('th').length - groupIndex;
                            $groupRow.append(`<td colspan="${colspan}" class="fw-bold dx-group-cell"><i class="fas fa-chevron-down me-2 dx-group-toggle" style="cursor: pointer;"></i>${group.label}: ${currentValue}</td>`);
                            $tbody.append($groupRow);
                        }
                    });
                    
                    for (var i = 0; i < activeGroups.length; i++) $dataRow.prepend('<td class="dx-group-indent"></td>');
                    
                    activeGroups.forEach(function(group) {
                        var idx = dataFieldIndexes[group.field];
                        if (idx !== undefined) $dataRow.find('td').eq(activeGroups.length + idx).addClass('dx-grouped-data').empty();
                    });

                    $tbody.append($dataRow);
                });
                
                $tbody.find('.dx-group-toggle').on('click', function() {
                    var $btn = $(this);
                    $btn.toggleClass('fa-chevron-right fa-chevron-down');
                    // Toggle logic implementation here...
                });
            }

            if (activeGroups.length > 0) setTimeout(renderGroupedData, 0);
            updateGroupAreaMessage();
        });
    }

    // ==================== 2. ÖZET BİLGİLER (SUMMARY) ====================
    function initSummaryFooter($grid) {
        $grid.find('tfoot.dx-summary-footer').remove();
        if ($grid.find('th[data-summary-field="true"]').length === 0) return;
        
        var $tfoot = $('<tfoot class="dx-summary-footer bg-light fw-bold"></tfoot>');
        var $footerRow = $('<tr></tr>');
        
        $grid.find('th.dx-sortable').each(function() {
            var $td = $('<td class="dx-summary-cell"></td>');
            if ($(this).attr('data-summary-field') === 'true') {
                var type = $(this).data('type');
                var colIndex = $(this).index();
                var isNumeric = type === 'number' || type === 'currency';
                
                var total = 0, count = 0, dates = [];
                $grid.find('tbody tr:not(.dx-group-row)').each(function() {
                    var txt = $(this).find('td').eq(colIndex).text().trim();
                    if (isNumeric) {
                        var val = parseFloat(txt.replace(/[^\d.-]/g, ''));
                        if (!isNaN(val)) { total += val; count++; }
                    } else if (type === 'datetime') {
                        var d = parseDate(txt);
                        if (d) dates.push(d);
                    } else { count++; }
                });

                if (isNumeric && count > 0) {
                    $td.html(`${total.toLocaleString('tr-TR')}<br><small class="text-muted">Ø ${(total/count).toFixed(2)}</small>`);
                } else if (type === 'datetime' && dates.length > 0) {
                    var min = new Date(Math.min.apply(null, dates));
                    var max = new Date(Math.max.apply(null, dates));
                    $td.html(`${min.toLocaleDateString()}<br><small>↔ ${max.toLocaleDateString()}</small>`);
                } else {
                    $td.html(`${count}<br><small class="text-muted">kayıt</small>`);
                }
                $td.addClass('dx-summary-active');
            } else {
                $td.addClass('dx-summary-inactive').html('<small>-</small>');
            }
            $footerRow.append($td);
        });
        
        if ($grid.find('th.dx-grid-actions').length) $footerRow.append('<td></td>');
        $tfoot.append($footerRow);
        $grid.append($tfoot);
    }

    // ==================== 3. DİĞER ÖZELLİKLER (Search, Sort, Filter) ====================
    function initColumnChooser() { /* ... Mevcut Kodunuz ... */ }
    
    function initGlobalSearch() {
        $('.dx-grid-filter').each(function() {
            var $search = $(this).attr('placeholder', '🔍 Ara...');
            var gridId = $search.data('target');
            var timeout;
            $search.on('keyup', function() {
                clearTimeout(timeout);
                var val = $(this).val().toLowerCase();
                timeout = setTimeout(function() {
                    var $rows = $('#dx-grid-' + gridId + ' tbody tr:not(.dx-group-row)');
                    $rows.each(function() {
                        $(this).toggle($(this).text().toLowerCase().indexOf(val) > -1);
                    });
                }, 300);
            });
        });
    }

    function initColumnFiltering() {
        $(document).on('change keyup', '.dx-column-filter', function(e) {
            if (e.type === 'keyup' && e.key !== 'Enter') return;
            var params = new URLSearchParams(window.location.search);
            params.set('page', 1);
            $('.dx-column-filter').each(function() {
                var val = $(this).val().trim();
                val ? params.set($(this).data('field'), val) : params.delete($(this).data('field'));
            });
            window.location.href = window.location.pathname + '?' + params.toString();
        });
    }

    // ==================== 4. AKILLI AJAX / SİLME İŞLEMİ (GÜNCELLENEN KISIM) ====================
    function initAjaxActions() {
        // Selector: datagrid-action olanlar, data-action="delete" olanlar ve title="Sil" olanlar
        var actionSelector = '.datagrid-action[data-type="ajax"], [data-action="delete"], button[title="Sil"]';

        $(document).off('click', actionSelector).on('click', actionSelector, function(e) {
            e.preventDefault();
            var btn = $(this);
            
            // 1. URL Belirleme
            var url = btn.attr('data-url') || btn.attr('href');
            
            // Eğer URL yoksa ve silme butonuysa URL'yi otomatik üret
            if (!url) {
                var action = btn.data('action'); // "delete"
                var id = btn.data('id');         // "2"
                
                if (action === 'delete' && id) {
                    var path = window.location.pathname; // "/kasa" veya "/kasa/"
                    if (path.endsWith('/')) path = path.slice(0, -1);
                    
                    // Otomatik URL: /kasa/sil/2
                    url = path + '/sil/' + id;
                    debugOutput('Otomatik URL Üretildi: ' + url);
                }
            }

            // 2. Kontrol
            if (!url || url === '#' || url === 'javascript:void(0);') {
                Swal.fire('Hata', 'İşlem adresi (URL) bulunamadı.', 'error');
                return;
            }

            // 3. Onay ve Gönderim
            Swal.fire({
                title: 'Emin misiniz?',
                text: "Bu kayıt silinecek! Bu işlem geri alınamaz.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Evet, Sil!',
                cancelButtonText: 'İptal'
            }).then((result) => {
                if (result.isConfirmed) {
                    sendAjaxRequest(url, btn);
                }
            });
        });
    }

    function sendAjaxRequest(url, btn) {
        // CSRF Token'ı HTML'den al
        var csrfToken = $('meta[name="csrf-token"]').attr('content');
        $.ajax({
            url: url,
            type: 'POST',
            dataType: 'json',
            // 👇 GÜVENLİK ANAHTARI BURADA EKLENİYOR
            headers: {
                "X-CSRFToken": csrfToken
            },
            beforeSend: function() {
                btn.prop('disabled', true);
                var icon = btn.find('i');
                if(icon.length) {
                    btn.data('original-icon', icon.attr('class'));
                    icon.attr('class', 'fas fa-spinner fa-spin');
                }
            },
            success: function(response) {
                if (response.success) {
                    Swal.fire({
                        title: 'Başarılı!',
                        text: response.message,
                        icon: 'success',
                        timer: 1500,
                        showConfirmButton: false
                    });
                    // Satırı kaldır
                    btn.closest('tr').fadeOut(500, function() { $(this).remove(); });
                } else {
                    Swal.fire('Hata!', response.message || 'İşlem başarısız.', 'error');
                }
            },
            error: function(xhr) {
                var msg = xhr.responseJSON && xhr.responseJSON.message ? xhr.responseJSON.message : "Sunucu hatası.";
                Swal.fire('Hata!', msg, 'error');
            },
            complete: function() {
                btn.prop('disabled', false);
                var icon = btn.find('i');
                if(icon.length && btn.data('original-icon')) {
                    icon.attr('class', btn.data('original-icon'));
                }
            }
        });
    }

    // ==================== BAŞLATMA (INIT) ====================
    function initDataGrid() {
        debugOutput('DataGrid Core JS Initializing...');
        
        initGrouping();
        initColumnFiltering();
        initGlobalSearch();
        initAjaxActions(); // Yeni Akıllı Silme
        
        // Özet Footer'ı başlat
        $('.dx-grid[data-enable-summary="true"]').each(function() {
            initSummaryFooter($(this));
        });
    }

    $(document).ready(function() {
        initDataGrid();
    });

})(window, jQuery);