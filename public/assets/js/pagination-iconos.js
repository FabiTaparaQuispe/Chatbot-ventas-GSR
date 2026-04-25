
(function () {
    'use strict';

    function pagesToShow(currentPage0Based, totalPages) {
        if (totalPages <= 0) return [];
        if (totalPages <= 7) {
            var p = [];
            for (var i = 1; i <= totalPages; i++) p.push(i);
            return p;
        }
        var current = currentPage0Based + 1;
        var set = {};
        set[1] = true;
        set[totalPages] = true;
        for (var i2 = Math.max(1, current - 2); i2 <= Math.min(totalPages, current + 2); i2++) set[i2] = true;
        var sorted = Object.keys(set)
            .map(Number)
            .sort(function (a, b) {
                return a - b;
            });
        var out = [];
        for (var j = 0; j < sorted.length; j++) {
            if (j > 0 && sorted[j] - sorted[j - 1] > 1) out.push('...');
            out.push(sorted[j]);
        }
        return out;
    }

    window.buildPaginationIconos = function (info) {
        var pages = pagesToShow(info.page, info.pages);
        var infoText =
            'Mostrando ' + (info.start + 1) + ' a ' + info.end + ' de ' + info.recordsDisplay + ' registros';
        var html = '<span class="dataTables_info">' + infoText + '</span>';
        html += '<span class="dataTables_paginate paginate_button_wrap">';
        html +=
            '<span class="paginate_button previous' +
            (info.page === 0 ? ' disabled' : '') +
            '" data-page="prev" role="button">Anterior</span>';
        for (var i3 = 0; i3 < pages.length; i3++) {
            if (pages[i3] === '...') {
                html += '<span class="paginate_button ellipsis" role="button">...</span>';
            } else {
                var isCurrent = pages[i3] === info.page + 1;
                html +=
                    '<span class="paginate_button' +
                    (isCurrent ? ' current' : '') +
                    '" data-page="' +
                    (pages[i3] - 1) +
                    '" role="button">' +
                    pages[i3] +
                    '</span>';
            }
        }
        html +=
            '<span class="paginate_button next' +
            (info.page >= info.pages - 1 ? ' disabled' : '') +
            '" data-page="next" role="button">Siguiente</span>';
        html += '</span>';
        return html;
    };

    if (typeof window.jQuery !== 'undefined') {
        jQuery(document).on('click', '.paginate_button_wrap .paginate_button', function () {
            var $btn = jQuery(this);
            if ($btn.hasClass('disabled') || $btn.hasClass('ellipsis')) return;
            var $container = $btn.closest('[data-table], [data-page-handler]');
            if (!$container.length) return;
            var tableSel = $container.attr('data-table');
            var page = $btn.attr('data-page');
            var pageNum = page === 'prev' ? 'prev' : page === 'next' ? 'next' : parseInt(page, 10);
            if (tableSel) {
                var dt = jQuery(tableSel).DataTable();
                if (!dt) return;
                if (page === 'prev') dt.page('previous').draw(false);
                else if (page === 'next') dt.page('next').draw(false);
                else if (!isNaN(pageNum)) dt.page(pageNum).draw(false);
            } else {
                var handler = $container.attr('data-page-handler');
                if (handler && typeof window[handler] === 'function') window[handler](pageNum);
            }
        });
    }
})();

