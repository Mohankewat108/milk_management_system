/* Accessible Bikram Sambat date picker. Calendar arithmetic is supplied by Django's
   nepali-datetime package so month lengths and weekday offsets stay authoritative. */
(() => {
  "use strict";
  const localeDigits = "०१२३४५६७८९";
  const asciiDigits = value => String(value).replace(/[०-९]/g, digit => String(localeDigits.indexOf(digit)));
  const localDigits = value => String(value).replace(/[0-9]/g, digit => localeDigits[Number(digit)]);
  const monthNames = ["बैशाख","जेठ","असार","साउन","भदौ","असोज","कार्तिक","मंसिर","पुष","माघ","फागुन","चैत"];
  const weekDays = ["सोम","मंगल","बुध","बिही","शुक्र","शनि","आइत"];
  const apiUrl = document.documentElement.dataset.nepaliCalendarApi || "/api/calendar/nepali/";
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const parse = value => {
    const match = asciiDigits(value).trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    return match ? {year:Number(match[1]),month:Number(match[2]),day:Number(match[3])} : null;
  };
  const pad = value => String(value).padStart(2, "0");

  document.querySelectorAll("input[data-calendar-date][data-calendar='bs']").forEach(input => {
    if (input.dataset.calendarReady) return;
    input.dataset.calendarReady = "true";
    const wrapper = make("div", "bs-date-control");
    input.parentNode.insertBefore(wrapper, input);
    wrapper.append(input);
    const trigger = make("button", "bs-date-trigger", "▦");
    trigger.type = "button";
    trigger.setAttribute("aria-label", "क्यालेन्डर खोल्नुहोस्");
    trigger.setAttribute("aria-haspopup", "dialog");
    wrapper.append(trigger);

    const popover = make("section", "bs-calendar");
    popover.hidden = true;
    popover.setAttribute("role", "dialog");
    popover.setAttribute("aria-label", "विक्रम संवत् मिति चयन");
    popover.setAttribute("aria-modal", "false");
    const header = make("div", "bs-calendar-header");
    const previous = make("button", "bs-calendar-nav", "‹");
    previous.type = "button";
    previous.setAttribute("aria-label", "अघिल्लो महिना");
    const heading = make("strong", "bs-calendar-heading");
    const next = make("button", "bs-calendar-nav", "›");
    next.type = "button";
    next.setAttribute("aria-label", "अर्को महिना");
    header.append(previous, heading, next);
    const grid = make("div", "bs-calendar-grid");
    grid.setAttribute("role", "grid");
    const footer = make("div", "bs-calendar-footer");
    const todayButton = make("button", "bs-calendar-today", "आज");
    todayButton.type = "button";
    const clearButton = make("button", "bs-calendar-clear", "मेटाउनुहोस्");
    clearButton.type = "button";
    footer.append(todayButton, clearButton);
    popover.append(header, grid, footer);
    wrapper.append(popover);

    let visible = null;
    let monthData = null;
    let requestSequence = 0;
    const close = () => {
      popover.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    };
    const open = () => {
      const selected = parse(input.value);
      const now = new Date();
      visible = selected || {year:now.getFullYear()+57,month:1,day:1};
      // The authoritative current BS month comes from the API; use a safe initial month
      // and replace it with the server's current month when no value is present.
      if (!selected) visible = null;
      popover.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      loadMonth(visible);
    };
    const shiftMonth = delta => {
      if (!visible) return;
      let year = visible.year, month = visible.month + delta;
      if (month < 1) { month = 12; year -= 1; }
      if (month > 12) { month = 1; year += 1; }
      visible = {year,month,day:1};
      loadMonth(visible);
    };
    const choose = (day, gregorian) => {
      const value = visible.year + "-" + pad(visible.month) + "-" + pad(day);
      input.value = localDigits(value);
      input.dataset.gregorianDate = gregorian;
      input.dispatchEvent(new Event("input", {bubbles:true}));
      input.dispatchEvent(new Event("change", {bubbles:true}));
      close();
    };
    const render = data => {
      monthData = data;
      visible = {year:data.year,month:data.month,day:1};
      heading.textContent = data.month_name + " " + localDigits(data.year);
      grid.replaceChildren();
      weekDays.forEach(day => {
        const label = make("span", "bs-calendar-weekday", day);
        label.setAttribute("role", "columnheader");
        grid.append(label);
      });
      for (let blank=0; blank<data.first_weekday; blank++) {
        const spacer = make("span", "bs-calendar-empty");
        spacer.setAttribute("aria-hidden", "true");
        grid.append(spacer);
      }
      data.days.forEach(item => {
        const button = make("button", "bs-calendar-day", localDigits(item.day));
        button.type = "button";
        button.setAttribute("role", "gridcell");
        button.setAttribute("aria-label", data.year + "-" + pad(data.month) + "-" + pad(item.day));
        const today = data.today.year===data.year && data.today.month===data.month && data.today.day===item.day;
        const selected = parse(input.value);
        if (today) { button.classList.add("is-today"); button.setAttribute("aria-current","date"); }
        if (selected && selected.year===data.year && selected.month===data.month && selected.day===item.day) {
          button.classList.add("is-selected"); button.setAttribute("aria-pressed","true");
        }
        button.addEventListener("click", () => choose(item.day,item.gregorian));
        grid.append(button);
      });
    };
    const loadMonth = async requested => {
      const sequence = ++requestSequence;
      try {
        let query = "";
        if (requested) query = "?year=" + encodeURIComponent(requested.year) + "&month=" + encodeURIComponent(requested.month);
        const response = await fetch(apiUrl + query, {headers:{"Accept":"application/json"},credentials:"same-origin"});
        if (!response.ok) throw new Error("Calendar data unavailable");
        const data = await response.json();
        if (sequence === requestSequence) render(data);
      } catch (error) {
        if (sequence === requestSequence) {
          grid.replaceChildren(make("p","bs-calendar-error","क्यालेन्डर लोड हुन सकेन। पुनः प्रयास गर्नुहोस्।"));
        }
      }
    };
    trigger.addEventListener("click", () => popover.hidden ? open() : close());
    previous.addEventListener("click", () => shiftMonth(-1));
    next.addEventListener("click", () => shiftMonth(1));
    todayButton.addEventListener("click", async () => {
      visible = null;
      await loadMonth(null);
      if (monthData) choose(monthData.today.day, monthData.days[monthData.today.day-1].gregorian);
    });
    clearButton.addEventListener("click", () => {
      input.value = "";
      delete input.dataset.gregorianDate;
      input.dispatchEvent(new Event("input",{bubbles:true}));
      input.dispatchEvent(new Event("change",{bubbles:true}));
      close();
    });
    input.addEventListener("focus", () => { if (popover.hidden) open(); });
    input.addEventListener("keydown", event => {
      if (event.key === "Escape") close();
      if (event.key === "ArrowDown" && popover.hidden) { event.preventDefault(); open(); }
    });
    document.addEventListener("pointerdown", event => {
      if (!wrapper.contains(event.target)) close();
    });
  });
})();
