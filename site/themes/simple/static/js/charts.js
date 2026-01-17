const routeSelect = document.getElementById("route-filter");
const dateSelect = document.getElementById("date-filter");
const chartGrid = document.getElementById("chart-grid");
const chartStatus = document.getElementById("chart-status");

if (routeSelect && dateSelect && chartGrid) {
  const chartCards = Array.from(chartGrid.querySelectorAll(".chart-card"));
  const chartData = chartCards.map((card) => ({
    card,
    route: card.dataset.route || "",
    date: card.dataset.date || "",
  }));

  const uniqueSorted = (items) =>
    Array.from(new Set(items)).sort((a, b) => a.localeCompare(b));
  const allRoutes = uniqueSorted(chartData.map((item) => item.route));
  const allDates = uniqueSorted(chartData.map((item) => item.date));

  const buildOptions = (select, values, label, selectedValue) => {
    select.innerHTML = "";
    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = label;
    select.appendChild(allOption);

    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });

    select.value = selectedValue;
  };

  const getAvailableDates = (selectedRoute) => {
    if (selectedRoute === "all") {
      return allDates;
    }
    return uniqueSorted(
      chartData
        .filter((item) => item.route === selectedRoute)
        .map((item) => item.date),
    );
  };

  const getAvailableRoutes = (selectedDate) => {
    if (selectedDate === "all") {
      return allRoutes;
    }
    return uniqueSorted(
      chartData
        .filter((item) => item.date === selectedDate)
        .map((item) => item.route),
    );
  };

  const updateFilters = () => {
    let selectedRoute = routeSelect.value || "all";
    let selectedDate = dateSelect.value || "all";

    const availableDates = getAvailableDates(selectedRoute);
    const availableRoutes = getAvailableRoutes(selectedDate);

    if (selectedRoute !== "all" && !availableRoutes.includes(selectedRoute)) {
      selectedRoute = "all";
    }
    if (selectedDate !== "all" && !availableDates.includes(selectedDate)) {
      selectedDate = "all";
    }

    buildOptions(routeSelect, availableRoutes, "All routes", selectedRoute);
    buildOptions(dateSelect, availableDates, "All dates", selectedDate);
  };

  const updateView = () => {
    const selectedRoute = routeSelect.value;
    const selectedDate = dateSelect.value;
    let visibleCount = 0;

    chartCards.forEach((card) => {
      const matches =
        (selectedRoute === "all" || card.dataset.route === selectedRoute) &&
        (selectedDate === "all" || card.dataset.date === selectedDate);
      card.style.display = matches ? "flex" : "none";
      if (matches) {
        visibleCount += 1;
      }
    });

    if (chartStatus) {
      const total = chartCards.length;
      chartStatus.textContent = `${visibleCount} of ${total} charts shown`;
    }
  };

  const syncAndUpdate = () => {
    updateFilters();
    updateView();
  };

  routeSelect.addEventListener("change", syncAndUpdate);
  dateSelect.addEventListener("change", syncAndUpdate);
  updateFilters();
  updateView();

  const modal = document.getElementById("chart-modal");
  const modalImage = modal?.querySelector(".chart-modal__image");
  const modalCaption = modal?.querySelector(".chart-modal__caption");
  const modalCloseTargets = modal?.querySelectorAll("[data-modal-close]") || [];

  const openModal = (card) => {
    if (!modal || !modalImage) {
      return;
    }
    const img = card.querySelector("img");
    if (!img) {
      return;
    }
    modalImage.src = img.src;
    modalImage.alt = img.alt;
    if (modalCaption) {
      modalCaption.textContent = `${card.dataset.route || ""} · ${
        card.dataset.date || ""
      }`;
    }
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  };

  const closeModal = () => {
    if (!modal || !modalImage) {
      return;
    }
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    modalImage.src = "";
    document.body.classList.remove("modal-open");
  };

  chartCards.forEach((card) => {
    card.addEventListener("click", () => openModal(card));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openModal(card);
      }
    });
  });

  modalCloseTargets.forEach((target) => {
    target.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal();
    }
  });
} else if (chartStatus) {
  chartStatus.textContent = "No charts available.";
}
