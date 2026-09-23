/* Шаканукова Лариса Тольбиевна — интерфейсные скрипты */
(function () {
  "use strict";

  /* --- Мобильное меню: выезжающая панель --- */
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  var backdrop = document.querySelector(".nav-backdrop");
  var scrollLock = 0;

  if (toggle && nav) {
    var focusables = function () {
      return nav.querySelectorAll("a[href], button:not([disabled])");
    };

    var setMenu = function (open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);

      if (backdrop) {
        if (open) {
          backdrop.hidden = false;
          requestAnimationFrame(function () { backdrop.classList.add("is-visible"); });
        } else {
          backdrop.classList.remove("is-visible");
          setTimeout(function () { if (!nav.classList.contains("is-open")) backdrop.hidden = true; }, 300);
        }
      }

      if (open) {
        // фиксируем страницу, чтобы фон не прокручивался под панелью
        scrollLock = window.scrollY;
        document.body.classList.add("nav-locked");
        document.body.style.top = -scrollLock + "px";
        document.body.style.position = "fixed";
        document.body.style.width = "100%";
        var first = focusables()[0];
        if (first) first.focus({ preventScroll: true });
      } else {
        document.body.classList.remove("nav-locked");
        document.body.style.position = "";
        document.body.style.top = "";
        document.body.style.width = "";
        window.scrollTo(0, scrollLock);
      }
    };

    var isOpen = function () { return toggle.getAttribute("aria-expanded") === "true"; };

    toggle.addEventListener("click", function () { setMenu(!isOpen()); });
    if (backdrop) backdrop.addEventListener("click", function () { setMenu(false); });

    nav.addEventListener("click", function (e) {
      if (e.target.closest("a") && isOpen()) setMenu(false);
    });

    document.addEventListener("keydown", function (e) {
      if (!isOpen()) return;
      if (e.key === "Escape") { setMenu(false); toggle.focus(); return; }
      if (e.key !== "Tab") return;
      // не выпускаем фокус за пределы панели
      var items = Array.prototype.slice.call(focusables());
      items.unshift(toggle);
      if (!items.length) return;
      var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });

    // возврат к десктопу с открытым меню не должен блокировать страницу
    var wide = window.matchMedia("(min-width: 861px)");
    var onWide = function (ev) { if (ev.matches && isOpen()) setMenu(false); };
    if (wide.addEventListener) wide.addEventListener("change", onWide);
    else if (wide.addListener) wide.addListener(onWide);
  }

  /* --- Тень у шапки при прокрутке --- */
  var header = document.querySelector(".header");
  if (header) {
    var onScroll = function () {
      header.classList.toggle("is-stuck", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* --- Плавное появление блоков --- */
  var reveals = document.querySelectorAll(".reveal");
  if (reveals.length) {
    if (!("IntersectionObserver" in window) ||
        window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      reveals.forEach(function (el) { el.classList.add("is-visible"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
      reveals.forEach(function (el) { io.observe(el); });
    }
  }

  /* --- Аккордеон: одновременно открыт один пункт --- */
  document.querySelectorAll("[data-accordion]").forEach(function (group) {
    var items = group.querySelectorAll("details");
    items.forEach(function (item) {
      item.addEventListener("toggle", function () {
        if (!item.open) return;
        items.forEach(function (other) { if (other !== item) other.open = false; });
      });
    });
  });

  /* --- Форма: анти-спам + письмо в почтовом клиенте --- */
  var form = document.querySelector("[data-mailto]");
  if (form) {
    var loadedAt = Date.now();
    var minSeconds = parseInt(form.getAttribute("data-min-seconds"), 10) || 4;
    var status = form.querySelector("[data-form-status]");
    var defaultNote = status ? status.textContent : "";

    var say = function (text, isError) {
      if (!status) return;
      status.textContent = text;
      status.classList.toggle("form__note--error", !!isError);
    };

    var looksLikeSpam = function (text) {
      var links = (text.match(/https?:\/\/|www\.|\[url|<a\s/gi) || []).length;
      var cyrillic = (text.match(/[а-яё]/gi) || []).length;
      // несколько ссылок подряд или текст вообще без кириллицы и длиной с рекламный блок
      return links >= 2 || (cyrillic === 0 && text.length > 200);
    };

    form.addEventListener("submit", function (e) {
      e.preventDefault();

      // 1. Honeypot: поле скрыто от человека, боты его заполняют
      if (form.elements.website && form.elements.website.value !== "") {
        say("Не удалось отправить сообщение. Напишите, пожалуйста, в WhatsApp или Telegram.", true);
        return;
      }

      // 2. Тайм-трап: человек не заполняет форму за пару секунд
      if ((Date.now() - loadedAt) / 1000 < minSeconds) {
        say("Проверьте, пожалуйста, поля и попробуйте ещё раз.", true);
        return;
      }

      // 3. Согласие на обработку персональных данных (152-ФЗ)
      var consent = form.elements.consent;
      var consentBox = form.querySelector(".consent");
      if (consent && !consent.checked) {
        if (consentBox) consentBox.classList.add("consent--error");
        say("Чтобы отправить заявку, отметьте согласие на обработку персональных данных.", true);
        consent.focus();
        return;
      }
      if (consentBox) consentBox.classList.remove("consent--error");

      var name = (form.elements.name.value || "").trim();
      var contact = (form.elements.contact.value || "").trim();
      var message = (form.elements.message.value || "").trim();

      // 4. Простая валидация
      if (name.length < 2 || contact.length < 5 || message.length < 10) {
        say("Заполните, пожалуйста, имя, контакт и пару слов о запросе.", true);
        return;
      }
      if (message.length > 4000) {
        say("Сообщение слишком длинное — сократите, пожалуйста, до 4000 знаков.", true);
        return;
      }

      // 5. Эвристика по содержимому
      if (looksLikeSpam(message + " " + name)) {
        say("Сообщение не отправлено: уберите, пожалуйста, ссылки из текста.", true);
        return;
      }

      var to = form.getAttribute("data-mailto");
      var body = [
        "Имя: " + name,
        "Контакт для ответа: " + contact,
        "",
        message,
        "",
        "---",
        "Согласие на обработку персональных данных дано " + new Date().toLocaleString("ru-RU") +
        " на странице " + window.location.href
      ].join("\n");

      window.location.href = "mailto:" + to +
        "?subject=" + encodeURIComponent("Заявка на консультацию — " + name) +
        "&body=" + encodeURIComponent(body);

      say("Открываем почтовый клиент с готовым письмом. Если этого не произошло — напишите на " + to + " или в мессенджер.", false);
    });

    form.addEventListener("input", function () {
      if (status && status.classList.contains("form__note--error")) say(defaultNote, false);
    });
  }

  /* --- Текущий год в подвале --- */
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });
})();
