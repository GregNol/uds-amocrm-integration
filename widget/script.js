define(['jquery'], function($) {
  var CustomWidget = function() {
    var self = this;

    this.getUdsDomain = function() {
      var wSettings = self.get_settings() || {};
      return wSettings.uds_domain || 'admin.uds.app';
    };

    this.getCardData = function() {
      var data = {
        order_id: null,
        customer_id: null,
        phone: null,
        email: null,
        lead_id: null,
        contact_id: null
      };

      try {
        var card = (window.AMOCRM && window.AMOCRM.data && window.AMOCRM.data.current_card) || {};
        data.lead_id = card.id || null;

        var wSettings = self.get_settings() || {};
        var configuredOrderField = (wSettings.cf_order_id || '').trim();
        var configuredCustomerField = (wSettings.cf_customer_id || '').trim();

        // 1. Поиск в custom_fields модели сделки/контакта
        var model = card.model ? card.model.attributes : {};
        var customFields = model.custom_fields || [];

        // Если custom_fields это объект или массив
        if (customFields && customFields.length) {
          for (var i = 0; i < customFields.length; i++) {
            var cf = customFields[i];
            var fId = String(cf.id || '');
            var fName = String(cf.name || '').toLowerCase();
            var fCode = String(cf.code || '').toLowerCase();
            var val = (cf.values && cf.values[0] && cf.values[0].value) ? String(cf.values[0].value).trim() : '';

            if (!val) continue;

            // Проверка поля заказа
            if (configuredOrderField && (fId === configuredOrderField || fName === configuredOrderField.toLowerCase() || fCode === configuredOrderField.toLowerCase())) {
              data.order_id = val;
            } else if (!data.order_id && (fName.indexOf('uds') !== -1 || fName.indexOf('order') !== -1 || fName.indexOf('заказ') !== -1) && (fName.indexOf('id') !== -1 || fName.indexOf('номер') !== -1 || fName.indexOf('№') !== -1)) {
              data.order_id = val;
            }

            // Проверка поля клиента
            if (configuredCustomerField && (fId === configuredCustomerField || fName === configuredCustomerField.toLowerCase() || fCode === configuredCustomerField.toLowerCase())) {
              data.customer_id = val;
            } else if (!data.customer_id && (fName.indexOf('uds') !== -1 || fName.indexOf('клиент') !== -1 || fName.indexOf('customer') !== -1) && (fName.indexOf('id') !== -1 || fName.indexOf('номер') !== -1)) {
              data.customer_id = val;
            }
          }
        }

        // 2. Поиск в DOM-полях (на случай несохраненных изменений или скрытых полей)
        if (!data.order_id || !data.customer_id) {
          $('input.custom-field, .linked-form__field, .control-phone, input[name*="cf"]').each(function() {
            var $inp = $(this);
            var name = ($inp.attr('name') || '').toLowerCase();
            var placeholder = ($inp.attr('placeholder') || '').toLowerCase();
            var label = ($inp.closest('.linked-form__field').find('.control--suggest--title, label').text() || '').toLowerCase();
            var val = ($inp.val() || '').trim();

            if (!val) return;

            if (!data.order_id && (name.indexOf('uds') !== -1 || label.indexOf('uds') !== -1 || label.indexOf('номер заказа') !== -1) && (label.indexOf('заказ') !== -1 || name.indexOf('order') !== -1)) {
              data.order_id = val;
            }

            if (!data.customer_id && (name.indexOf('uds') !== -1 || label.indexOf('uds') !== -1) && (label.indexOf('клиент') !== -1 || name.indexOf('customer') !== -1)) {
              data.customer_id = val;
            }
          });
        }

        // 3. Поиск телефона контакта
        if (model.main_contact && model.main_contact.phone) {
          data.phone = model.main_contact.phone;
        } else {
          var phoneVal = $('input[name*="PHONE"], input.control-phone').first().val();
          if (phoneVal) data.phone = phoneVal.trim();
        }

        // 4. Поиск в ленте примечаний/событий карточки (если ID не найдены в полях)
        if (!data.order_id || !data.customer_id) {
          var feedText = $('.notes-wrapper, .feed-compose, .feed-note').text() || '';
          
          if (!data.order_id) {
            var orderMatch = feedText.match(/admin\.(?:get)?uds\.app\/admin\/orders\?order=([a-zA-Z0-9_-]+)/i) ||
                             feedText.match(/ЗАКАЗ\s*№\s*([a-zA-Z0-9_-]+)/i) ||
                             feedText.match(/UDS заказ\s*([a-zA-Z0-9_-]+)/i);
            if (orderMatch && orderMatch[1]) {
              data.order_id = orderMatch[1].trim();
            }
          }

          if (!data.customer_id) {
            var custMatch = feedText.match(/admin\.(?:get)?uds\.app\/admin\/customers\/([a-zA-Z0-9_-]+)/i) ||
                            feedText.match(/ССЫЛКА НА КЛИЕНТА В UDS:[^\d]*(\d+)/i) ||
                            feedText.match(/клиент[^\d]*UDS[^\d]*([a-zA-Z0-9_-]+)/i);
            if (custMatch && custMatch[1]) {
              data.customer_id = custMatch[1].trim();
            }
          }
        }
      } catch (err) {
        console.error('[UDS Widget] Ошибка получения данных карточки:', err);
      }

      return data;
    };

    this.openUdsModal = function(params) {
      var title = params.title || 'UDS Панель';
      var url = params.url;
      var icon = params.icon || '🚀';

      $('#uds-modal-overlay').remove();

      var modalHtml = 
        '<div id="uds-modal-overlay">' +
          '<div class="uds-modal-window">' +
            '<div class="uds-modal-header">' +
              '<div class="uds-modal-title">' +
                '<span style="font-size: 18px;">' + icon + '</span>' +
                '<span>' + title + '</span>' +
              '</div>' +
              '<div class="uds-modal-actions">' +
                '<a href="' + url + '" target="_blank" rel="noopener noreferrer" class="uds-modal-btn">' +
                  '<span>↗ В новой вкладке</span>' +
                '</a>' +
                '<button type="button" class="uds-modal-btn uds-btn-reload" title="Обновить">' +
                  '<span>🔄 Обновить</span>' +
                '</button>' +
                '<button type="button" class="uds-modal-btn uds-btn-fs" title="На весь экран">' +
                  '<span>⛶</span>' +
                '</button>' +
                '<button type="button" class="uds-modal-close-btn" title="Закрыть (Esc)">✕</button>' +
              '</div>' +
            '</div>' +
            '<div class="uds-modal-body">' +
              '<div class="uds-modal-loader">' +
                '<div class="uds-spinner"></div>' +
                '<div>Загрузка интерфейса UDS...</div>' +
              '</div>' +
              '<iframe id="uds-modal-iframe" src="' + url + '" allow="clipboard-read; clipboard-write"></iframe>' +
            '</div>' +
            '<div class="uds-modal-footer">' +
              '<span>💡 Если требуется авторизация — войдите под аккаунтом администратора UDS</span>' +
              '<a href="' + url + '" target="_blank" rel="noopener noreferrer">Прямая ссылка на UDS: ' + url + '</a>' +
            '</div>' +
          '</div>' +
        '</div>';

      var $modal = $(modalHtml).appendTo('body');
      var $iframe = $modal.find('#uds-modal-iframe');
      var $loader = $modal.find('.uds-modal-loader');
      var $window = $modal.find('.uds-modal-window');

      $iframe.on('load', function() {
        $loader.fadeOut(150);
      });

      $modal.find('.uds-btn-reload').on('click', function() {
        $loader.show();
        $iframe.attr('src', url);
      });

      $modal.find('.uds-btn-fs').on('click', function() {
        $window.toggleClass('uds-fullscreen');
      });

      var closeModal = function() {
        $modal.fadeOut(150, function() {
          $modal.remove();
        });
        $(document).off('keydown.udsModal');
      };

      $modal.find('.uds-modal-close-btn').on('click', closeModal);

      $modal.on('click', function(e) {
        if ($(e.target).is('#uds-modal-overlay')) {
          closeModal();
        }
      });

      $(document).on('keydown.udsModal', function(e) {
        if (e.keyCode === 27) { // Escape
          closeModal();
        }
      });
    };

    this.renderRightPanel = function() {
      $('#uds-widget-container').remove();

      var cardData = self.getCardData();
      var domain = self.getUdsDomain();

      var orderUrl = cardData.order_id ? ('https://' + domain + '/admin/orders?order=' + encodeURIComponent(cardData.order_id)) : null;
      
      // Чат: если есть customer_id -> /admin/customers/{id}/messages, иначе /admin/messages
      var chatUrl = null;
      if (cardData.customer_id) {
        chatUrl = 'https://' + domain + '/admin/customers/' + encodeURIComponent(cardData.customer_id) + '/messages';
      } else if (cardData.order_id) {
        chatUrl = orderUrl; // fallback на страницу заказа
      } else {
        chatUrl = 'https://' + domain + '/admin/messages';
      }

      var customerUrl = cardData.customer_id ? ('https://' + domain + '/admin/customers/' + encodeURIComponent(cardData.customer_id) + '/info') : null;

      var html = '<div id="uds-widget-container" class="uds-widget-card">';
      
      // Header
      html += 
        '<div class="uds-widget-header">' +
          '<div class="uds-widget-title-wrap">' +
            '<span class="uds-widget-logo-badge">UDS</span>' +
            '<span class="uds-widget-title">UDS Интеграция</span>' +
          '</div>' +
          (cardData.order_id || cardData.customer_id ? '<span class="uds-widget-badge">Активно</span>' : '') +
        '</div>';

      // Data summary
      if (cardData.order_id || cardData.customer_id) {
        if (cardData.order_id) {
          html += 
            '<div class="uds-widget-info-row">' +
              '<span>Заказ UDS:</span>' +
              '<span class="uds-widget-info-val">№ ' + cardData.order_id + '</span>' +
            '</div>';
        }
        if (cardData.customer_id) {
          html += 
            '<div class="uds-widget-info-row">' +
              '<span>Клиент UDS:</span>' +
              '<span class="uds-widget-info-val">ID ' + cardData.customer_id + '</span>' +
            '</div>';
        }

        // Action Buttons
        html += '<div class="uds-widget-buttons">';

        // 1. Чат с клиентом
        if (chatUrl) {
          html += 
            '<div class="uds-btn-row">' +
              '<button type="button" class="uds-btn uds-btn-primary js-uds-open-chat" style="flex: 1;">' +
                '<span>💬 Открыть чат UDS</span>' +
              '</button>' +
              '<a href="' + chatUrl + '" target="_blank" rel="noopener noreferrer" class="uds-btn uds-btn-outline uds-btn-icon-only" title="Открыть чат в новой вкладке">↗</a>' +
            '</div>';
        }

        // 2. Заказ в UDS
        if (orderUrl) {
          html += 
            '<div class="uds-btn-row">' +
              '<button type="button" class="uds-btn uds-btn-secondary js-uds-open-order" style="flex: 1;">' +
                '<span>📦 Посмотреть заказ</span>' +
              '</button>' +
              '<a href="' + orderUrl + '" target="_blank" rel="noopener noreferrer" class="uds-btn uds-btn-outline uds-btn-icon-only" title="Открыть заказ в новой вкладке">↗</a>' +
            '</div>';
        }

        // 3. Профиль клиента
        if (customerUrl) {
          html += 
            '<div class="uds-btn-row">' +
              '<button type="button" class="uds-btn uds-btn-outline js-uds-open-customer" style="flex: 1;">' +
                '<span>👤 Профиль клиента</span>' +
              '</button>' +
              '<a href="' + customerUrl + '" target="_blank" rel="noopener noreferrer" class="uds-btn uds-btn-outline uds-btn-icon-only" title="Открыть профиль в новой вкладке">↗</a>' +
            '</div>';
        }

        html += '</div>';
      } else {
        html += 
          '<div class="uds-empty-hint">' +
            'В этой сделке пока нет ID заказа или клиента UDS.' +
            '<div style="margin-top: 6px;">' +
              '<a href="https://' + domain + '/admin/orders" target="_blank" class="uds-btn uds-btn-outline" style="margin-top: 4px;">' +
                '<span>Перейти в панель UDS ↗</span>' +
              '</a>' +
            '</div>' +
          '</div>';
      }

      html += '</div>';

      // Вставляем виджет в правую панель карточки
      var $container = $('.card-widgets, .card-holder .card-widgets__item, #widgets-block, .js-card-widgets').first();
      if ($container.length) {
        $container.prepend(html);
      } else {
        // Fallback: вставляем в правую колонку карточки
        var $rightCol = $('.card-entity-form__right-column, .card-right-column, .card-widgets-container').first();
        if ($rightCol.length) {
          $rightCol.prepend(html);
        } else {
          $('.card-holder').append(html);
        }
      }

      // Привязка событий клика
      var $widget = $('#uds-widget-container');

      $widget.find('.js-uds-open-chat').on('click', function(e) {
        e.preventDefault();
        self.openUdsModal({
          title: 'UDS Чат с клиентом' + (cardData.customer_id ? ' (ID ' + cardData.customer_id + ')' : ''),
          url: chatUrl,
          icon: '💬'
        });
      });

      $widget.find('.js-uds-open-order').on('click', function(e) {
        e.preventDefault();
        self.openUdsModal({
          title: 'UDS Заказ № ' + (cardData.order_id || ''),
          url: orderUrl,
          icon: '📦'
        });
      });

      $widget.find('.js-uds-open-customer').on('click', function(e) {
        e.preventDefault();
        self.openUdsModal({
          title: 'UDS Профиль клиента (ID ' + (cardData.customer_id || '') + ')',
          url: customerUrl,
          icon: '👤'
        });
      });
    };

    this.callbacks = {
      render: function() {
        return true;
      },
      init: function() {
        return true;
      },
      bind_actions: function() {
        self.renderRightPanel();
        return true;
      },
      settings: function() {
        return true;
      },
      onSave: function() {
        return true;
      },
      destroy: function() {
        $('#uds-widget-container').remove();
        $('#uds-modal-overlay').remove();
        return true;
      }
    };

    return this;
  };

  return CustomWidget;
});
