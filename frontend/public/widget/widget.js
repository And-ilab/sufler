/**
 * Belarusbank online-chat embed widget — UI aligned with canvases/online-chat-mockups
 * «Виджет клиента»: форма входа → диалог (ожидание оператора).
 *
 * Usage:
 *   <script
 *     src="/widget/widget.js"
 *     data-widget-id="site-belarusbank"
 *     data-placement="website"
 *     defer
 *   ></script>
 */
(function (global) {
  'use strict';

  var SCRIPT = document.currentScript;
  var WIDGET_ID =
    (SCRIPT && SCRIPT.getAttribute('data-widget-id')) || 'demo-widget';
  var PLACEMENT =
    (SCRIPT && SCRIPT.getAttribute('data-placement')) || 'website';
  var API_BASE =
    (SCRIPT && SCRIPT.getAttribute('data-api-base')) || '';
  var LOGO_SRC =
    (SCRIPT && SCRIPT.getAttribute('data-logo-src')) ||
    '/assets/belarusbank-logo.png';
  var LOCALE = 'ru';

  /** Palette from online-chat-mockups WIDGET_PALETTE */
  var WP = {
    headerBrand: '#2B6B4A',
    headerNeutral: '#FAFBFA',
    headerAccentLine: '#3A7D5C',
    primary: '#2E7D52',
    primaryHover: '#256B45',
    primaryWeak: '#D4EBDC',
    accent: '#3A7D5C',
    accentMuted: '#4A8B6A',
    clientBubbleBg: '#E8F5EE',
    clientBubbleBorder: '#B8D9C8',
    clientBubbleText: '#1F4D35',
    operatorBubbleBg: '#F5F5F4',
    chatBg: '#F7F9F8',
    footerBg: '#EEF2EF',
    composerBg: '#FAFBFA',
    fabBg: '#2E7D52',
    fabBadge: '#C62828',
    avatarOperator: '#3A7D5C',
    avatarClient: '#B8D9C8',
    stroke: '#D5DBE8',
    text: '#1F2A24',
    textSecondary: '#5A6B62',
    textTertiary: '#7A8A82',
    surface: '#ffffff',
    font: '"Segoe UI",system-ui,-apple-system,sans-serif',
    radius: 12,
    width: 380,
  };

  var STR = {
    fab: 'Онлайн-чат',
    title: 'Онлайн-консультант',
    bank: 'Беларусбанк',
    welcome: 'Здравствуйте! Чем можем помочь?',
    operatorsOnline: 'Операторы онлайн',
    nameLabel: 'Имя',
    namePlaceholder: 'Анна',
    lastNameLabel: 'Фамилия',
    lastNamePlaceholder: 'Козлова',
    phoneLabel: 'Телефон',
    phonePlaceholder: '+375 29 123-45-67',
    questionLabel: 'Задайте Ваш вопрос',
    questionPlaceholder: 'Опишите ваш вопрос…',
    send: 'Отправить',
    placeholder: 'Напишите сообщение…',
    attach: 'Прикрепить файл',
    close: 'Закрыть',
    you: 'Вы',
    operatorName: 'Мария Соколова',
    operatorShort: 'Мария',
    operatorRole: 'Оператор поддержки',
    operatorInitials: 'МС',
    joined: 'Мария подключилась к диалогу',
    typing: 'оператор печатает…',
    online: 'в сети',
    waiting: 'Ожидаем ответа оператора…',
    requiredHint: 'Заполните все поля',
  };

  function cssText() {
    return [
      ':host{all:initial;font-family:' + WP.font + ';}',
      '*{box-sizing:border-box;}',
      '.root{position:fixed;right:20px;bottom:20px;z-index:2147483000;color:' +
        WP.text +
        ';}',
      '.fab{width:60px;height:60px;border:0;border-radius:30px;cursor:pointer;',
      'background:' +
        WP.fabBg +
        ';box-shadow:0 8px 24px rgba(23,32,51,.16);',
      'display:flex;align-items:center;justify-content:center;position:relative;padding:0;overflow:hidden;}',
      '.fab img{width:44px;height:44px;border-radius:8px;object-fit:cover;display:block;}',
      '.fab-badge{position:absolute;top:-2px;right:-2px;min-width:18px;height:18px;border-radius:9px;',
      'padding:0 5px;background:' +
        WP.fabBadge +
        ';color:#fff;font-size:10px;font-weight:600;',
      'display:flex;align-items:center;justify-content:center;}',
      '.fab[aria-expanded="true"]{display:none;}',
      '.panel{width:' +
        WP.width +
        'px;max-width:calc(100vw - 32px);height:560px;max-height:calc(100vh - 40px);',
      'display:flex;flex-direction:column;overflow:hidden;border-radius:' +
        WP.radius +
        'px;',
      'background:' +
        WP.surface +
        ';border:1px solid ' +
        WP.stroke +
        ';box-shadow:0 12px 40px rgba(15,28,22,.16);}',
      '.panel[hidden]{display:none!important;}',
      '.header{position:relative;display:flex;align-items:center;gap:10px;',
      'padding:14px 16px;padding-right:48px;}',
      '.header--brand{background:' + WP.headerBrand + ';color:#fff;}',
      '.header--neutral{background:' +
        WP.headerNeutral +
        ';border-bottom:2px solid ' +
        WP.headerAccentLine +
        ';}',
      '.header-logo{width:32px;height:32px;border-radius:6px;object-fit:cover;flex-shrink:0;display:block;}',
      '.header-title{font-size:14px;font-weight:600;line-height:1.25;}',
      '.header--brand .header-title{color:#fff;}',
      '.header--neutral .header-title{color:' + WP.headerBrand + ';}',
      '.header-sub{font-size:11px;margin-top:1px;line-height:1.3;}',
      '.header--brand .header-sub{color:#fff;opacity:.92;}',
      '.header--neutral .header-sub{color:' + WP.accentMuted + ';}',
      '.win{position:absolute;top:0;right:0;display:flex;height:100%;}',
      '.win button{width:44px;height:100%;border:0;background:transparent;cursor:pointer;',
      'font-size:18px;line-height:1;padding:0;display:flex;align-items:center;justify-content:center;}',
      '.header--brand .win button{color:rgba(255,255,255,.92);}',
      '.header--neutral .win button{color:' + WP.textSecondary + ';}',
      '.win button:hover{background:rgba(0,0,0,.06);}',
      '.header--brand .win button:hover{background:rgba(255,255,255,.12);}',
      '.prechat{flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column;',
      'padding:20px;gap:14px;background:' + WP.chatBg + ';}',
      '.welcome{font-size:16px;line-height:1.45;font-weight:500;color:' + WP.text + ';}',
      '.pill-online{display:inline-block;align-self:flex-start;font-size:11px;font-weight:600;color:' +
        WP.accentMuted +
        ';background:' +
        WP.primaryWeak +
        ';padding:4px 10px;border-radius:10px;}',
      '.fields{display:grid;grid-template-columns:1fr 1fr;gap:12px;}',
      '.field label{display:block;font-size:12px;font-weight:600;margin-bottom:6px;color:' +
        WP.text +
        ';}',
      '.field input,.field textarea,.composer input{width:100%;padding:8px 10px;',
      'border:1px solid ' +
        WP.stroke +
        ';border-radius:6px;font:inherit;font-size:13px;background:#fff;color:' +
        WP.text +
        ';resize:vertical;}',
      '.field input{min-height:36px;padding:0 10px;}',
      '.field textarea{min-height:110px;line-height:1.4;}',
      '.field input:focus,.field textarea:focus,.composer input:focus{outline:2px solid ' +
        WP.primaryWeak +
        ';border-color:' +
        WP.primary +
        ';}',
      '.field input.invalid,.field textarea.invalid{border-color:#C62828;outline:2px solid rgba(198,40,40,.18);}',
      '.field-error{font-size:11px;color:#C62828;margin-top:2px;min-height:14px;}',
      '.btn{border:1px solid ' +
        WP.primary +
        ';border-radius:6px;background:' +
        WP.primary +
        ';color:#fff;font:inherit;font-size:13px;font-weight:600;',
      'cursor:pointer;line-height:1.2;padding:8px 14px;}',
      '.btn:hover{background:' + WP.primaryHover + ';border-color:' + WP.primaryHover + ';}',
      '.btn:disabled{opacity:.55;cursor:not-allowed;}',
      '.btn--block{width:100%;margin-top:4px;}',
      '.btn--sm{padding:6px 12px;font-size:12px;flex-shrink:0;}',
      '.op-strip{padding:10px 16px;background:' +
        WP.footerBg +
        ';border-bottom:1px solid ' +
        WP.clientBubbleBorder +
        ';display:flex;align-items:center;gap:8px;}',
      '.op-strip[hidden]{display:none!important;}',
      '.avatar{width:28px;height:28px;border-radius:14px;display:flex;align-items:center;justify-content:center;',
      'font-size:10px;font-weight:600;color:#fff;flex-shrink:0;}',
      '.op-meta{flex:1;min-width:0;}',
      '.op-name{font-size:12px;font-weight:600;color:' + WP.text + ';}',
      '.op-role{font-size:11px;color:' + WP.textSecondary + ';}',
      '.op-online{font-size:11px;font-weight:600;color:' +
        WP.accentMuted +
        ';background:' +
        WP.primaryWeak +
        ';padding:3px 8px;border-radius:10px;flex-shrink:0;}',
      '.messages{flex:1;min-height:0;overflow:auto;padding:16px;display:flex;flex-direction:column;gap:12px;',
      'background:' + WP.chatBg + ';}',
      '.sys{text-align:center;font-size:11px;color:' + WP.accentMuted + ';padding:6px 0;}',
      '.waiting{text-align:center;font-size:12px;color:' + WP.textSecondary + ';padding:8px 0 4px;}',
      '.row{display:flex;gap:8px;align-items:flex-end;}',
      '.row--client{justify-content:flex-end;}',
      '.row--operator{justify-content:flex-start;}',
      '.bubble{max-width:78%;padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.45;}',
      '.bubble--client{background:' +
        WP.clientBubbleBg +
        ';border:1px solid ' +
        WP.clientBubbleBorder +
        ';color:' +
        WP.clientBubbleText +
        ';border-bottom-right-radius:4px;}',
      '.bubble--operator{background:' +
        WP.operatorBubbleBg +
        ';border:1px solid ' +
        WP.stroke +
        ';color:' +
        WP.text +
        ';border-bottom-left-radius:4px;}',
      '.bubble-label{font-size:10px;margin-bottom:4px;}',
      '.bubble--client .bubble-label{color:' + WP.accentMuted + ';}',
      '.bubble--operator .bubble-label{color:' + WP.textTertiary + ';}',
      '.bubble-time{font-size:10px;margin-top:6px;text-align:right;}',
      '.bubble--client .bubble-time{color:' + WP.accentMuted + ';}',
      '.bubble--operator .bubble-time{color:' + WP.textTertiary + ';}',
      '.typing{display:flex;align-items:center;gap:6px;padding-left:36px;}',
      '.typing[hidden]{display:none!important;}',
      '.typing-dots{display:flex;gap:4px;padding:8px 12px;border-radius:12px;background:' +
        WP.operatorBubbleBg +
        ';border:1px solid ' +
        WP.stroke +
        ';}',
      '.typing-dots span{width:6px;height:6px;border-radius:3px;background:' +
        WP.accentMuted +
        ';display:inline-block;}',
      '.typing-label{font-size:11px;color:' + WP.accentMuted + ';}',
      '.composer{padding:16px;border-top:1px solid ' +
        WP.clientBubbleBorder +
        ';background:' +
        WP.composerBg +
        ';display:flex;gap:8px;align-items:center;}',
      '.icon-btn{width:32px;height:32px;border:1px solid ' +
        WP.stroke +
        ';border-radius:6px;background:' +
        WP.footerBg +
        ';color:' +
        WP.accent +
        ';cursor:pointer;font-size:16px;line-height:1;flex-shrink:0;}',
      '.chat-body{flex:1;min-height:0;display:flex;flex-direction:column;}',
      '.chat-body[hidden],.prechat[hidden]{display:none!important;}',
    ].join('');
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatTime(date) {
    var h = date.getHours();
    var m = date.getMinutes();
    return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
  }

  function createWidget() {
    var host = document.createElement('div');
    host.id = 'bb-chat-widget-host';
    host.setAttribute('data-widget-id', WIDGET_ID);
    host.setAttribute('data-placement', PLACEMENT);
    host.setAttribute('data-locale', LOCALE);
    host.setAttribute('data-testid', 'bb-chat-widget');
    document.body.appendChild(host);

    var shadow = host.attachShadow({ mode: 'open' });
    var style = document.createElement('style');
    style.textContent = cssText();
    shadow.appendChild(style);

    var root = document.createElement('div');
    root.className = 'root';
    root.innerHTML =
      '<button type="button" class="fab" aria-expanded="false" aria-controls="bb-widget-panel" data-testid="widget-fab" title="' +
      STR.fab +
      '">' +
      '<img src="' +
      escapeHtml(LOGO_SRC) +
      '" alt="" />' +
      '<span class="fab-badge" aria-hidden="true">1</span>' +
      '</button>' +
      '<section class="panel" id="bb-widget-panel" hidden data-testid="widget-panel" role="dialog" aria-label="' +
      STR.title +
      '">' +
      '<header class="header header--brand" data-header>' +
      '<img class="header-logo" src="' +
      escapeHtml(LOGO_SRC) +
      '" alt="Беларусбанк" />' +
      '<div style="flex:1;min-width:0">' +
      '<div class="header-title">' +
      STR.title +
      '</div>' +
      '<div class="header-sub" data-header-sub>' +
      STR.bank +
      '</div>' +
      '</div>' +
      '<div class="win">' +
      '<button type="button" data-action="close" aria-label="' +
      STR.close +
      '" title="' +
      STR.close +
      '">×</button>' +
      '</div>' +
      '</header>' +
      '<div class="prechat" data-view="prechat">' +
      '<div class="welcome">' +
      STR.welcome +
      '</div>' +
      '<span class="pill-online">' +
      STR.operatorsOnline +
      '</span>' +
      '<div class="fields">' +
      '<div class="field"><label for="bb-widget-name">' +
      STR.nameLabel +
      ' *</label>' +
      '<input id="bb-widget-name" type="text" data-testid="widget-name" placeholder="' +
      STR.namePlaceholder +
      '" autocomplete="given-name" required /></div>' +
      '<div class="field"><label for="bb-widget-last-name">' +
      STR.lastNameLabel +
      ' *</label>' +
      '<input id="bb-widget-last-name" type="text" data-testid="widget-last-name" placeholder="' +
      STR.lastNamePlaceholder +
      '" autocomplete="family-name" required /></div>' +
      '</div>' +
      '<div class="field"><label for="bb-widget-phone">' +
      STR.phoneLabel +
      ' *</label>' +
      '<input id="bb-widget-phone" type="tel" data-testid="widget-phone" placeholder="' +
      STR.phonePlaceholder +
      '" autocomplete="tel" required /></div>' +
      '<div class="field">' +
      '<label for="bb-widget-question">' +
      STR.questionLabel +
      ' *</label>' +
      '<textarea id="bb-widget-question" data-testid="widget-question" placeholder="' +
      STR.questionPlaceholder +
      '" rows="4" required></textarea>' +
      '</div>' +
      '<div class="field-error" data-form-error hidden>' +
      STR.requiredHint +
      '</div>' +
      '<button type="button" class="btn btn--block" data-action="start" data-testid="widget-start">' +
      STR.send +
      '</button>' +
      '</div>' +
      '<div class="chat-body" data-view="chat" hidden>' +
      '<div class="op-strip" data-op-strip hidden>' +
      '<div class="avatar" style="background:' +
      WP.avatarOperator +
      '">' +
      STR.operatorInitials +
      '</div>' +
      '<div class="op-meta"><div class="op-name">' +
      STR.operatorName +
      '</div><div class="op-role">' +
      STR.operatorRole +
      '</div></div>' +
      '<span class="op-online">' +
      STR.online +
      '</span>' +
      '</div>' +
      '<div class="messages" data-testid="widget-messages"></div>' +
      '<div class="composer">' +
      '<button type="button" class="icon-btn" title="' +
      STR.attach +
      '" aria-label="' +
      STR.attach +
      '" data-action="attach">+</button>' +
      '<input type="text" data-testid="widget-input" placeholder="' +
      STR.placeholder +
      '" />' +
      '<button type="button" class="btn btn--sm" data-action="send" data-testid="widget-send">' +
      STR.send +
      '</button>' +
      '</div>' +
      '</div>' +
      '</section>';

    shadow.appendChild(root);

    var fab = root.querySelector('.fab');
    var panel = root.querySelector('.panel');
    var header = root.querySelector('[data-header]');
    var headerSub = root.querySelector('[data-header-sub]');
    var messagesEl = root.querySelector('[data-testid="widget-messages"]');
    var inputEl = root.querySelector('[data-testid="widget-input"]');
    var nameEl = root.querySelector('[data-testid="widget-name"]');
    var lastNameEl = root.querySelector('[data-testid="widget-last-name"]');
    var phoneEl = root.querySelector('[data-testid="widget-phone"]');
    var questionEl = root.querySelector('[data-testid="widget-question"]');
    var formErrorEl = root.querySelector('[data-form-error]');
    var opStrip = root.querySelector('[data-op-strip]');
    var state = {
      open: false,
      started: false,
      operatorConnected: false,
      clientInitials: 'АК',
      messages: [],
      dialogId: null,
      seenMessageIds: {},
      ws: null,
    };

    function apiUrl(path) {
      var base = (API_BASE || '').replace(/\/$/, '');
      return base + path;
    }

    function wsUrl(path) {
      var base = (API_BASE || '').replace(/\/$/, '');
      if (base) {
        try {
          var u = new URL(base);
          var proto = u.protocol === 'https:' ? 'wss:' : 'ws:';
          return proto + '//' + u.host + path;
        } catch (err) {
          /* fall through */
        }
      }
      var pageProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return pageProto + '//' + window.location.host + path;
    }

    function fullClientName() {
      return ((nameEl.value || '') + ' ' + (lastNameEl.value || '')).trim();
    }

    function setOpen(open) {
      state.open = open;
      fab.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) panel.removeAttribute('hidden');
      else panel.setAttribute('hidden', '');
    }

    function showChat(started) {
      state.started = started;
      root.querySelectorAll('[data-view]').forEach(function (node) {
        var view = node.getAttribute('data-view');
        var show = started ? view === 'chat' : view === 'prechat';
        if (show) node.removeAttribute('hidden');
        else node.setAttribute('hidden', '');
      });
      if (started) {
        header.classList.remove('header--brand');
        header.classList.add('header--neutral');
      } else {
        header.classList.add('header--brand');
        header.classList.remove('header--neutral');
      }
      headerSub.textContent = STR.bank;
    }

    function initialsFromName(name) {
      var parts = String(name || '')
        .trim()
        .split(/\s+/)
        .filter(Boolean);
      if (!parts.length) return 'АК';
      return parts
        .map(function (p) {
          return p.charAt(0);
        })
        .join('')
        .slice(0, 2)
        .toUpperCase();
    }

    function addSystem(text) {
      state.messages.push({ speaker: 'system', text: text });
      var el = document.createElement('div');
      el.className = 'sys';
      el.textContent = text;
      messagesEl.appendChild(el);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setWaitingHint(show) {
      var existing = messagesEl.querySelector('.waiting');
      if (existing) existing.remove();
      if (!show) return;
      var el = document.createElement('div');
      el.className = 'waiting';
      el.textContent = STR.waiting;
      messagesEl.appendChild(el);
    }

    function addBubble(speaker, text, label, initials, time) {
      state.messages.push({ speaker: speaker, text: text });
      var isClient = speaker === 'client';
      var row = document.createElement('div');
      row.className = 'row row--' + (isClient ? 'client' : 'operator');

      var avatarHtml =
        '<div class="avatar" style="background:' +
        (isClient ? WP.avatarClient : WP.avatarOperator) +
        ';color:' +
        (isClient ? WP.clientBubbleText : '#fff') +
        '">' +
        escapeHtml(initials || (isClient ? state.clientInitials : STR.operatorInitials)) +
        '</div>';

      var bubble =
        '<div class="bubble bubble--' +
        (isClient ? 'client' : 'operator') +
        '">' +
        '<div class="bubble-label">' +
        escapeHtml(label || (isClient ? STR.you : STR.operatorShort)) +
        '</div>' +
        '<div>' +
        escapeHtml(text) +
        '</div>' +
        (time
          ? '<div class="bubble-time">' + escapeHtml(time) + '</div>'
          : '') +
        '</div>';

      row.innerHTML = isClient ? bubble + avatarHtml : avatarHtml + bubble;
      messagesEl.appendChild(row);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    /** Call when operator joins the dialog (API/WS or demo hook). */
    function connectOperator(operatorName, options) {
      options = options || {};
      if (state.operatorConnected) return;
      state.operatorConnected = true;
      setWaitingHint(false);
      if (operatorName) {
        var nameNode = opStrip.querySelector('.op-name');
        if (nameNode) nameNode.textContent = operatorName;
      }
      opStrip.removeAttribute('hidden');
      if (options.announce !== false) {
        addSystem(STR.joined);
      }
    }

    /** Show/hide typing indicator. */
    function showTyping(show) {
      var existing = messagesEl.querySelector('.typing');
      if (existing) existing.remove();
      if (!show) return;
      var el = document.createElement('div');
      el.className = 'typing';
      el.innerHTML =
        '<div class="typing-dots"><span></span><span></span><span></span></div>' +
        '<span class="typing-label">' +
        STR.typing +
        '</span>';
      messagesEl.appendChild(el);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function rememberMessageId(id) {
      if (!id) return;
      state.seenMessageIds[id] = true;
    }

    function handleRemoteMessage(message) {
      if (!message || !message.id || state.seenMessageIds[message.id]) return;
      rememberMessageId(message.id);
      if (message.speaker === 'system') {
        addSystem(message.text);
        return;
      }
      if (message.speaker === 'operator') {
        setWaitingHint(false);
        if (!state.operatorConnected) connectOperator();
        addBubble(
          'operator',
          message.text,
          STR.operatorShort,
          STR.operatorInitials,
          formatTime(new Date(message.created_at || Date.now())),
        );
        return;
      }
      if (message.speaker === 'client') {
        /* Local client bubbles are already rendered; skip echoes. */
        return;
      }
    }

    function closeDialogSocket() {
      if (state.ws) {
        try {
          state.ws.close();
        } catch (err) {
          /* ignore */
        }
        state.ws = null;
      }
    }

    function connectDialogSocket(dialogId) {
      closeDialogSocket();
      if (!dialogId || typeof WebSocket === 'undefined') return;
      var socket = new WebSocket(wsUrl('/ws/online-chat/dialog/' + dialogId + '/'));
      state.ws = socket;
      socket.onmessage = function (event) {
        var data;
        try {
          data = JSON.parse(event.data);
        } catch (err) {
          return;
        }
        var type = data && data.type;
        var payload = (data && data.payload) || {};
        if (type === 'operator.joined') {
          connectOperator(payload.operator_name, {
            announce: !payload.system_message,
          });
          if (payload.system_message) handleRemoteMessage(payload.system_message);
          return;
        }
        if (type === 'message.created') {
          handleRemoteMessage(payload);
          return;
        }
        if (type === 'typing.start') {
          if (payload.speaker === 'operator') showTyping(true);
          return;
        }
        if (type === 'typing.stop') {
          if (payload.speaker === 'operator') showTyping(false);
        }
      };
    }

    function createDialog(text) {
      return fetch(apiUrl('/api/v1/online-chat/dialogs/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          widget_id: WIDGET_ID,
          placement: PLACEMENT,
          channel: 'widget',
          first_name: (nameEl.value || '').trim(),
          last_name: (lastNameEl.value || '').trim(),
          phone: (phoneEl.value || '').trim(),
          locale: LOCALE,
        }),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            if (!response.ok || !body.ok) {
              throw new Error((body && body.detail) || 'create_failed');
            }
            return body;
          });
        })
        .then(function (body) {
          state.dialogId = body.dialog && body.dialog.id;
          if (body.message && body.message.id) rememberMessageId(body.message.id);
          if (state.dialogId) connectDialogSocket(state.dialogId);
          return body;
        })
        .catch(function () {
          addSystem('Не удалось отправить обращение. Попробуйте ещё раз.');
        });
    }

    function postDialogMessage(text) {
      if (!state.dialogId) return;
      fetch(apiUrl('/api/v1/online-chat/dialogs/' + state.dialogId + '/messages/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, speaker: 'client' }),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            if (body && body.message && body.message.id) {
              rememberMessageId(body.message.id);
            }
          });
        })
        .catch(function () {});
    }

    function sendFromComposer() {
      var text = (inputEl.value || '').trim();
      if (!text) return;
      inputEl.value = '';
      setWaitingHint(false);
      addBubble(
        'client',
        text,
        STR.you,
        state.clientInitials,
        formatTime(new Date()),
      );
      if (!state.operatorConnected) setWaitingHint(true);
      postDialogMessage(text);
    }

    function clearFieldErrors() {
      ;[nameEl, lastNameEl, phoneEl, questionEl].forEach(function (el) {
        el.classList.remove('invalid');
      });
      if (formErrorEl) formErrorEl.setAttribute('hidden', '');
    }

    function validatePrechat() {
      clearFieldErrors();
      var firstName = (nameEl.value || '').trim();
      var lastName = (lastNameEl.value || '').trim();
      var phone = (phoneEl.value || '').trim();
      var question = (questionEl.value || '').trim();
      var missing = [];
      if (!firstName) missing.push(nameEl);
      if (!lastName) missing.push(lastNameEl);
      if (!phone) missing.push(phoneEl);
      if (!question) missing.push(questionEl);
      if (!missing.length) {
        return { firstName: firstName, lastName: lastName, phone: phone, question: question };
      }
      missing.forEach(function (el) {
        el.classList.add('invalid');
      });
      if (formErrorEl) formErrorEl.removeAttribute('hidden');
      missing[0].focus();
      return null;
    }

    ;[nameEl, lastNameEl, phoneEl, questionEl].forEach(function (el) {
      el.addEventListener('input', function () {
        el.classList.remove('invalid');
        if (
          (nameEl.value || '').trim() &&
          (lastNameEl.value || '').trim() &&
          (phoneEl.value || '').trim() &&
          (questionEl.value || '').trim()
        ) {
          if (formErrorEl) formErrorEl.setAttribute('hidden', '');
        }
      });
    });

    function startChat() {
      var form = validatePrechat();
      if (!form) return;
      state.clientInitials = initialsFromName(form.firstName + ' ' + form.lastName);
      state.operatorConnected = false;
      state.dialogId = null;
      state.seenMessageIds = {};
      closeDialogSocket();
      messagesEl.innerHTML = '';
      state.messages = [];
      opStrip.setAttribute('hidden', '');
      showChat(true);
      addBubble(
        'client',
        form.question,
        STR.you,
        state.clientInitials,
        formatTime(new Date()),
      );
      setWaitingHint(true);
      createDialog(form.question);
    }

    fab.addEventListener('click', function () {
      setOpen(true);
    });

    root.addEventListener('click', function (event) {
      var target = event.target;
      if (!(target instanceof Element)) return;
      var actionBtn = target.closest('[data-action]');
      if (!actionBtn) return;
      var action = actionBtn.getAttribute('data-action');
      if (action === 'close') {
        setOpen(false);
        return;
      }
      if (action === 'start') {
        startChat();
        return;
      }
      if (action === 'send') {
        sendFromComposer();
        return;
      }
    });

    inputEl.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        sendFromComposer();
      }
    });

    showChat(false);
    setOpen(false);

    global.BelarusbankChatWidget = {
      open: function () {
        setOpen(true);
      },
      close: function () {
        setOpen(false);
      },
      /** Demo/realtime hooks */
      connectOperator: connectOperator,
      showTyping: showTyping,
      widgetId: WIDGET_ID,
      placement: PLACEMENT,
      palette: WP,
      getDialogId: function () {
        return state.dialogId;
      },
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createWidget);
  } else {
    createWidget();
  }
})(typeof window !== 'undefined' ? window : this);
