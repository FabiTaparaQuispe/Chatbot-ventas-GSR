        </main>
    </div>
</div>

<?php if (empty($skipFloatingChat ?? null)): ?>
<?php include __DIR__ . '/../modules/chat_floating.inc.php'; ?>
<?php endif; ?>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<?php if (!empty($loadVentasAssets)): ?>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="assets/js/pagination-iconos.js"></script>
<?php endif; ?>
<script src="assets/js/theme.js"></script>
<script src="assets/js/sidebar-pin.js"></script>
<?php if (!empty($extraScripts)) { echo $extraScripts; } ?>
</body>
</html>

