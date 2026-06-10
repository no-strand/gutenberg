/**
 * Validação genérica de campos, mensagens de erro e contadores de formulários.
 * Créditos do projeto: Nostrand.
 */

(function(){
  /** Normalizespaces. Usada pelo fluxo principal da aplicação. */
  function normalizeSpaces(value){
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  /** Isvalidemail. Usada pelo fluxo principal da aplicação. */
  function isValidEmail(value){
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
  }

  /** Isvalidphone. Usada pelo fluxo principal da aplicação. */
  function isValidPhone(value){
    const compact = String(value || '').replace(/[^\d+]/g, '');
    const digits = compact.replace(/\D/g, '');
    return /^\+?\d+$/.test(compact) && digits.length >= 10 && digits.length <= 13;
  }

  /** Getlabelwrapper. Usada pelo fluxo principal da aplicação. */
  function getLabelWrapper(field){
    return field.closest('label') || field.parentElement;
  }

  /** Issupportedfield. Usada pelo fluxo principal da aplicação. */
  function isSupportedField(field){
    return field && !field.disabled && field.type !== 'hidden' && field.type !== 'file' && field.type !== 'checkbox';
  }

  /** Ishiddenfield. Usada pelo fluxo principal da aplicação. */
  function isHiddenField(field){
    if (!field) return true;
    const style = window.getComputedStyle(field);
    return style.display === 'none' || style.visibility === 'hidden' || !!field.closest('.oculto');
  }

  /** Ensuremeta. Usada pelo fluxo principal da aplicação. */
  function ensureMeta(field){
    if (!isSupportedField(field) || field.tagName === 'SELECT' || field.dataset.validationMetaReady === 'true') return;
    const wrapper = getLabelWrapper(field);
    if (!wrapper) return;
    const meta = document.createElement('div');
    meta.className = 'campo-validacao-wrap';
    const message = document.createElement('span');
    message.className = 'campo-validacao-mensagem';
    const counter = document.createElement('span');
    counter.className = 'campo-validacao-contador';
    meta.append(message, counter);
    wrapper.appendChild(meta);
    field.dataset.validationMetaReady = 'true';
  }

  /** Setfieldstate. Usada pelo fluxo principal da aplicação. */
  function setFieldState(field, state, messageText){
    const wrapper = getLabelWrapper(field);
    const meta = wrapper?.querySelector('.campo-validacao-wrap');
    const message = meta?.querySelector('.campo-validacao-mensagem');
    field.classList.remove('campo-estado-neutro', 'campo-estado-valido', 'campo-estado-invalido');
    if (field.tagName === 'SELECT') return;
    if (state === 'valid') field.classList.add('campo-estado-valido');
    else if (state === 'invalid') field.classList.add('campo-estado-invalido');
    else field.classList.add('campo-estado-neutro');
    if (message) message.textContent = messageText || '';
  }

  /** Updatecounter. Usada pelo fluxo principal da aplicação. */
  function updateCounter(field){
    const wrapper = getLabelWrapper(field);
    const counter = wrapper?.querySelector('.campo-validacao-contador');
    if (!counter) return;
    const max = Number(field.getAttribute('maxlength') || field.dataset.maxlength || 0);
    if (!max) { counter.textContent = ''; counter.classList.remove('limite'); return; }
    const size = String(field.value || '').length;
    counter.textContent = `${size}/${max}`;
    counter.classList.toggle('limite', size >= max);
  }

  /** Validatefield. Usada pelo fluxo principal da aplicação. */
  function validateField(field){
    if (!isSupportedField(field)) return true;
    ensureMeta(field);
    updateCounter(field);

    if (isHiddenField(field)) {
      setFieldState(field, 'neutral', '');
      return true;
    }

    const rawValue = String(field.value || '');
    const value = field.tagName === 'TEXTAREA' ? rawValue.trim() : normalizeSpaces(rawValue);
    const required = field.required;
    const max = Number(field.getAttribute('maxlength') || field.dataset.maxlength || 0);
    let invalidMessage = '';

    if (!value) {
      setFieldState(field, required ? 'invalid' : 'neutral', required ? window.t('validation.required_field') : '');
      return !required;
    }
    if (max && rawValue.length > max) invalidMessage = window.t('validation.max_characters', { max });
    if (!invalidMessage && field.dataset.validateContact === 'true' && !isValidEmail(value) && !isValidPhone(value)) {
      invalidMessage = window.t('validation.valid_email_or_phone');
    }
    if (!invalidMessage && field.type === 'number') {
      const numericValue = Number(field.value);
      const min = field.getAttribute('min');
      const maxNum = field.getAttribute('max');
      if (field.value === '' || Number.isNaN(numericValue)) invalidMessage = window.t('validation.valid_number');
      else if (min !== null && min !== '' && numericValue < Number(min)) invalidMessage = window.t('validation.min_value', { min });
      else if (maxNum !== null && maxNum !== '' && numericValue > Number(maxNum)) invalidMessage = window.t('validation.max_value', { max: maxNum });
    }
    if (!invalidMessage && field.getAttribute('pattern')) {
      try {
        const regex = new RegExp(`^(?:${field.getAttribute('pattern')})$`);
        if (!regex.test(field.value)) invalidMessage = window.t('validation.invalid_format');
      } catch (_) {}
    }

    if (invalidMessage) {
      setFieldState(field, 'invalid', invalidMessage);
      return false;
    }
    setFieldState(field, 'valid', '');
    return true;
  }

  /** Refreshformstate. Usada pelo fluxo principal da aplicação. */
  function refreshFormState(form){
    if (!(form instanceof HTMLFormElement)) return true;
    const fields = [...form.querySelectorAll('input, textarea, select')].filter(isSupportedField);
    let valid = true;
    fields.forEach((field) => {
      if (!validateField(field)) valid = false;
    });
    const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
    submitButtons.forEach((button) => {
      button.disabled = !valid;
      button.setAttribute('aria-disabled', valid ? 'false' : 'true');
    });
    return valid;
  }

  /** Bindfield. Usada pelo fluxo principal da aplicação. */
  function bindField(field){
    if (!isSupportedField(field) || field.dataset.validationBound === 'true') return;
    if (!field.closest('.modal')) return;
    field.dataset.validationBound = 'true';
    ensureMeta(field);
    /** Handler. Usada pelo fluxo principal da aplicação. */
    const handler = () => refreshFormState(field.form || field.closest('form'));
    field.addEventListener('input', handler);
    field.addEventListener('change', handler);
    field.addEventListener('blur', handler);
    requestAnimationFrame(handler);
  }

  /** Bindform. Usada pelo fluxo principal da aplicação. */
  function bindForm(form){
    if (!(form instanceof HTMLFormElement) || form.dataset.validationFormBound === 'true') return;
    if (!form.closest('.modal')) return;
    form.dataset.validationFormBound = 'true';
    form.addEventListener('submit', (event) => {
      if (!refreshFormState(form)) event.preventDefault();
    });
    requestAnimationFrame(() => refreshFormState(form));
  }

  /** Bindall. Usada pelo fluxo principal da aplicação. */
  function bindAll(root=document){
    root.querySelectorAll('.modal input, .modal textarea, .modal select').forEach(bindField);
    root.querySelectorAll('.modal form').forEach(bindForm);
  }

  /** Refreshmodal. Usada pelo fluxo principal da aplicação. */
  function refreshModal(modal){
    if (!modal) return true;
    bindAll(modal);
    let valid = true;
    modal.querySelectorAll('form').forEach((form) => {
      if (!refreshFormState(form)) valid = false;
    });
    return valid;
  }

  window.validacaoCampos = {
    refreshField: validateField,
    refreshFormState,
    refreshModal,
    bindAll,
  };

  document.addEventListener('DOMContentLoaded', () => {
    bindAll(document);
    const observer = new MutationObserver(() => bindAll(document));
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  });
})();
