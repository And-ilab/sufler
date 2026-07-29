/**
 * Belarusbank online-chat embed widget (FR-CC-09 / FR-CHAT-01).
 * Shadow DOM · RU locale · minimal footprint · design tokens.
 *
 * Usage:
 *   <script
 *     src="https://…/widget/widget.js"
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
  var LOCALE = 'ru';

  /** Belarusbank styling tokens (frontend/src/tokens.css) + widget accents. */
  var TOKENS = {
    primary: '#0D3880',
    primaryDark: '#0A2A66',
    secondary: '#E31E24',
    surface: '#ffffff',
    surfaceMuted: '#f5f7fb',
    text: '#172033',
    textMuted: '#5f6b7a',
    border: '#d9e0ea',
    success: '#16794b',
    successBg: '#e8f6ef',
    infoBg: '#eaf0fa',
    radius: '8px',
    shadow: '0 8px 24px rgba(23,32,51,.12)',
    font: 'Inter,"Segoe UI",Roboto,Helvetica,Arial,sans-serif',
    widgetAccent: '#2E7D52',
    widgetAccentHover: '#256B45',
    widgetHeader: '#2B6B4A',
    clientBubble: '#E8F5EE',
    operatorBubble: '#F5F5F4',
    chatBg: '#F7F9F8',
  };

  var STR = {
    fab: 'Онлайн-чат',
    title: 'Беларусбанк',
    subtitle: 'Онлайн-консультант',
    welcome: 'Здравствуйте! Чем можем помочь?',
    nameLabel: 'Как к вам обращаться',
    namePlaceholder: 'Имя (необязательно)',
    start: 'Начать диалог',
    placeholder: 'Введите сообщение…',
    send: 'Отправить',
    channels: 'Другие каналы',
    telegram: 'Telegram',
    viber: 'Viber',
    close: 'Закрыть',
    minimize: 'Свернуть',
    online: 'операторы на связи',
    offline: 'сейчас ответим в рабочее время',
    typing: 'Оператор печатает…',
    you: 'Вы',
    operator: 'Оператор',
    placementHint: 'Точка размещения',
  };

  function cssText() {
    return [
      ':host{all:initial;font-family:' + TOKENS.font + ';}',
      '*{box-sizing:border-box;}',
      '.root{position:fixed;right:20px;bottom:20px;z-index:2147483000;color:' +
        TOKENS.text +
        ';}',
      '.fab{width:56px;height:56px;border:0;border-radius:50%;cursor:pointer;',
      'background:' +
        TOKENS.widgetAccent +
        ';color:#fff;box-shadow:' +
        TOKENS.shadow +
        ';',
      'display:grid;place-items:center;font-size:13px;font-weight:700;}',
      '.fab:hover{background:' + TOKENS.widgetAccentHover + ';}',
      '.fab[aria-expanded="true"]{display:none;}',
      '.panel{width:360px;max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 40px);',
      'display:flex;flex-direction:column;overflow:hidden;border-radius:12px;',
      'background:' +
        TOKENS.surface +
        ';border:1px solid ' +
        TOKENS.border +
        ';box-shadow:' +
        TOKENS.shadow +
        ';}',
      '.panel[hidden]{display:none!important;}',
      '.header{display:flex;align-items:center;justify-content:space-between;gap:8px;',
      'padding:12px 14px;background:' +
        TOKENS.widgetHeader +
        ';color:#fff;}',
      '.header h2{margin:0;font-size:15px;font-weight:700;}',
      '.header p{margin:2px 0 0;font-size:11px;opacity:.9;}',
      '.header-actions{display:flex;gap:4px;}',
      '.icon-btn{width:28px;height:28px;border:0;border-radius:6px;background:rgba(255,255,255,.16);',
      'color:#fff;cursor:pointer;font-size:14px;line-height:1;}',
      '.body{flex:1;min-height:0;display:flex;flex-direction:column;background:' +
        TOKENS.chatBg +
        ';}',
      '.prechat,.messages{padding:14px;overflow:auto;}',
      '.messages{flex:1;display:flex;flex-direction:column;gap:8px;}',
      '.bubble{max-width:85%;padding:8px 10px;border-radius:10px;font-size:13px;line-height:1.4;}',
      '.bubble small{display:block;margin-bottom:2px;font-size:10px;opacity:.75;}',
      '.bubble--client{align-self:flex-end;background:' +
        TOKENS.clientBubble +
        ';color:#1F4D35;}',
      '.bubble--operator{align-self:flex-start;background:' +
        TOKENS.operatorBubble +
        ';}',
      '.meta{padding:8px 14px;font-size:11px;color:' +
        TOKENS.textMuted +
        ';border-top:1px solid ' +
        TOKENS.border +
        ';}',
      '.channels{display:flex;gap:8px;padding:0 14px 10px;}',
      '.chip{flex:1;min-height:34px;border:1px solid ' +
        TOKENS.border +
        ';border-radius:' +
        TOKENS.radius +
        ';',
      'background:' +
        TOKENS.surface +
        ';color:' +
        TOKENS.primary +
        ';font:inherit;font-size:12px;font-weight:600;cursor:pointer;}',
      '.chip:hover{background:' + TOKENS.infoBg + ';}',
      '.composer{display:flex;gap:8px;padding:10px 14px;border-top:1px solid ' +
        TOKENS.border +
        ';background:' +
        TOKENS.surfaceMuted +
        ';}',
      '.composer input,.prechat input{flex:1;min-height:36px;padding:0 10px;border:1px solid ' +
        TOKENS.border +
        ';border-radius:' +
        TOKENS.radius +
        ';font:inherit;font-size:13px;}',
      '.btn{min-height:36px;padding:0 12px;border:0;border-radius:' +
        TOKENS.radius +
        ';background:' +
        TOKENS.widgetAccent +
        ';color:#fff;font:inherit;font-size:13px;font-weight:700;cursor:pointer;}',
      '.btn:hover{background:' + TOKENS.widgetAccentHover + ';}',
      '.btn:disabled{opacity:.55;cursor:not-allowed;}',
      '.prechat label{display:grid;gap:6px;margin:12px 0;font-size:12px;color:' +
        TOKENS.textMuted +
        ';}',
      '.status{display:inline-flex;align-items:center;gap:6px;margin-top:8px;font-size:12px;color:' +
        TOKENS.success +
        ';}',
      '.dot{width:8px;height:8px;border-radius:50%;background:' + TOKENS.success + ';}',
    ].join('');
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
      '">Чат</button>' +
      '<section class="panel" id="bb-widget-panel" hidden data-testid="widget-panel" role="dialog" aria-label="' +
      STR.title +
      '">' +
      '<header class="header">' +
      '<div><h2>' +
      STR.title +
      '</h2><p>' +
      STR.subtitle +
      '</p></div>' +
      '<div class="header-actions">' +
      '<button type="button" class="icon-btn" data-action="minimize" aria-label="' +
      STR.minimize +
      '">–</button>' +
      '<button type="button" class="icon-btn" data-action="close" aria-label="' +
      STR.close +
      '">×</button>' +
      '</div></header>' +
      '<div class="body">' +
      '<div class="prechat" data-view="prechat">' +
      '<p>' +
      STR.welcome +
      '</p>' +
      '<div class="status"><span class="dot"></span>' +
      STR.online +
      '</div>' +
      '<label>' +
      STR.nameLabel +
      '<input type="text" data-testid="widget-name" placeholder="' +
      STR.namePlaceholder +
      '" autocomplete="name" /></label>' +
      '<button type="button" class="btn" data-action="start" data-testid="widget-start">' +
      STR.start +
      '</button>' +
      '<p class="meta" style="border:0;padding:10px 0 0">' +
      STR.placementHint +
      ': <strong>' +
      PLACEMENT +
      '</strong> · id <code>' +
      WIDGET_ID +
      '</code></p>' +
      '</div>' +
      '<div class="messages" data-view="chat" hidden data-testid="widget-messages"></div>' +
      '</div>' +
      '<div class="channels" data-view="chat" hidden>' +
      '<button type="button" class="chip" data-channel="telegram" data-testid="widget-telegram">' +
      STR.telegram +
      '</button>' +
      '<button type="button" class="chip" data-channel="viber" data-testid="widget-viber">' +
      STR.viber +
      '</button>' +
      '</div>' +
      '<div class="composer" data-view="chat" hidden>' +
      '<input type="text" data-testid="widget-input" placeholder="' +
      STR.placeholder +
      '" />' +
      '<button type="button" class="btn" data-action="send" data-testid="widget-send">' +
      STR.send +
      '</button>' +
      '</div>' +
      '</section>';

    shadow.appendChild(root);

    var fab = root.querySelector('.fab');
    var panel = root.querySelector('.panel');
    var messagesEl = root.querySelector('[data-testid="widget-messages"]');
    var inputEl = root.querySelector('[data-testid="widget-input"]');
    var nameEl = root.querySelector('[data-testid="widget-name"]');
    var state = { open: false, started: false, messages: [] };

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
    }

    function addBubble(speaker, text) {
      state.messages.push({ speaker: speaker, text: text });
      var bubble = document.createElement('div');
      bubble.className =
        'bubble bubble--' + (speaker === 'client' ? 'client' : 'operator');
      bubble.innerHTML =
        '<small>' +
        (speaker === 'client' ? STR.you : STR.operator) +
        '</small>' +
        escapeHtml(text);
      messagesEl.appendChild(bubble);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    function mockOperatorReply(clientText) {
      window.setTimeout(function () {
        addBubble(
          'operator',
          'Спасибо за обращение. Мы получили ваше сообщение: «' +
            clientText.slice(0, 80) +
            '». Оператор скоро ответит.',
        );
      }, 450);
    }

    function postWidgetMessage(text) {
      if (!API_BASE) {
        mockOperatorReply(text);
        return;
      }
      fetch(
        API_BASE.replace(/\/$/, '') +
          '/api/v1/widget/' +
          encodeURIComponent(WIDGET_ID) +
          '/messages/',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            placement: PLACEMENT,
            locale: LOCALE,
          }),
        },
      )
        .then(function (response) {
          return response.json().catch(function () {
            return {};
          });
        })
        .then(function (body) {
          if (body && body.reply) addBubble('operator', body.reply);
          else mockOperatorReply(text);
        })
        .catch(function () {
          mockOperatorReply(text);
        });
    }

    function send() {
      var text = (inputEl.value || '').trim();
      if (!text) return;
      inputEl.value = '';
      addBubble('client', text);
      postWidgetMessage(text);
    }

    fab.addEventListener('click', function () {
      setOpen(true);
    });

    root.addEventListener('click', function (event) {
      var target = event.target;
      if (!(target instanceof Element)) return;
      var action = target.getAttribute('data-action');
      var channel = target.getAttribute('data-channel');
      if (action === 'close' || action === 'minimize') {
        setOpen(false);
        return;
      }
      if (action === 'start') {
        showChat(true);
        if (!state.messages.length) addBubble('operator', STR.welcome);
        return;
      }
      if (action === 'send') {
        send();
        return;
      }
      if (channel === 'telegram' || channel === 'viber') {
        addBubble(
          'operator',
          'Переход в ' +
            (channel === 'telegram' ? STR.telegram : STR.viber) +
            ' (mock). Сообщение будет доставлено через webhook-адаптер канала.',
        );
      }
    });

    inputEl.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        send();
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
      widgetId: WIDGET_ID,
      placement: PLACEMENT,
      tokens: TOKENS,
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createWidget);
  } else {
    createWidget();
  }
})(typeof window !== 'undefined' ? window : this);
