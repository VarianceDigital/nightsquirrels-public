// nightsquirrel/static/js/custom.js
(function () {
  function focusNoScroll(el) {
    if (!el) return;
    try {
      el.focus({ preventScroll: true });
    } catch (e) {
      // Fallback for older browsers
      try { el.focus(); } catch (_) {}
    }
  }

  function ensureGlobalFocusSink() {
    let sink = document.getElementById('nsGlobalFocusSink');
    if (sink) return sink;

    sink = document.createElement('div');
    sink.id = 'nsGlobalFocusSink';

    // Visually hidden but ACCESSIBLE
    sink.style.position = 'fixed';
    sink.style.width = '1px';
    sink.style.height = '1px';
    sink.style.overflow = 'hidden';
    sink.style.opacity = '0';
    sink.style.pointerEvents = 'none';

    // IMPORTANT:
    // - no aria-hidden
    // - no role
    // - tabindex required for focus
    sink.tabIndex = 0;

    document.body.appendChild(sink);
    return sink;
  }


  function yankFocusOutOfModal(focusSink) {
    focusNoScroll(focusSink);
    requestAnimationFrame(() => focusNoScroll(focusSink));
    setTimeout(() => focusNoScroll(focusSink), 0);
  }

  function wireModal(modalEl) {
    if (!modalEl || modalEl.dataset.nsFocusWired === '1') return;
    modalEl.dataset.nsFocusWired = '1';

    const focusSink = ensureGlobalFocusSink();
    let lastFocused = null;

    modalEl.addEventListener('show.bs.modal', () => {
      lastFocused = document.activeElement;
    });

    // KEY PART: remove focus BEFORE Bootstrap toggles aria-hidden on hide
    modalEl.addEventListener('hide.bs.modal', () => {
      yankFocusOutOfModal(focusSink);
    });

    // Capture phase: runs before Bootstrap's internal dismiss handlers.
    modalEl.addEventListener(
      'pointerdown',
      (e) => {
        const dismiss = e.target && e.target.closest && e.target.closest('[data-bs-dismiss="modal"]');
        if (dismiss) yankFocusOutOfModal(focusSink);
      },
      true
    );

    modalEl.addEventListener('hidden.bs.modal', () => {
      // Restore focus to the previously focused element if it still exists.
      if (lastFocused && document.contains(lastFocused) && typeof lastFocused.focus === 'function') {
        focusNoScroll(lastFocused);
      } else {
        // Fallback: focus body without scrolling
        focusNoScroll(document.body);
      }
    });
  }

  function wireAllExistingModals() {
    document.querySelectorAll('.modal').forEach(wireModal);
  }

  document.addEventListener('DOMContentLoaded', () => {
    wireAllExistingModals();

    // If modals are created dynamically, keep them covered:
    const mo = new MutationObserver(() => wireAllExistingModals());
    mo.observe(document.body, { childList: true, subtree: true });

    // Auto-show flash modal if present and marked
    const auto = document.querySelector('.modal[data-ns-autoshow="1"]');
    if (auto && window.bootstrap && bootstrap.Modal) {
      bootstrap.Modal.getOrCreateInstance(auto).show();
    }

    // ── Alert modal (replaces native alert()) ──
    var alertModal = document.getElementById('nsAlertModal');
    if (alertModal) {
      var alertBody = document.getElementById('nsAlertBody');
      var bsAlert   = bootstrap.Modal.getOrCreateInstance(alertModal);
      window.nsAlert = function (msg) {
        alertBody.textContent = msg;
        bsAlert.show();
      };
    }

    // ── Confirm modal (replaces native confirm()) ──
    var confirmModal = document.getElementById('nsConfirmModal');
    if (confirmModal) {
      var confirmBody = document.getElementById('nsConfirmBody');
      var confirmOk   = document.getElementById('nsConfirmOk');
      var bsConfirm   = bootstrap.Modal.getOrCreateInstance(confirmModal);
      var pendingAction = null;

      confirmOk.addEventListener('click', function () {
        bsConfirm.hide();
        if (pendingAction) pendingAction();
        pendingAction = null;
      });

      confirmModal.addEventListener('hidden.bs.modal', function () {
        pendingAction = null;
      });

      document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-confirm]');
        if (!btn) return;

        e.preventDefault();
        e.stopPropagation();
        confirmBody.textContent = btn.dataset.confirm;

        var form = btn.closest('form');

        if (btn.tagName === 'BUTTON' && btn.type === 'submit' && form) {
          // Button with name inside a form — inject hidden input so server sees the name
          pendingAction = function () {
            if (btn.name) {
              var h = document.createElement('input');
              h.type = 'hidden'; h.name = btn.name; h.value = btn.value || '';
              form.appendChild(h);
            }
            form.submit();
          };
        } else if (form && form.dataset.confirm) {
          // Form-level data-confirm
          pendingAction = function () { form.submit(); };
        }

        bsConfirm.show();
      }, true);
    }
  });
})();
