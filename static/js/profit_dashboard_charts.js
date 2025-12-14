(function () {
  const profitDataElement = document.getElementById("profit-dashboard-data");
  if (!profitDataElement) return;

  const profitData = JSON.parse(profitDataElement.textContent);

  const formatCurrency = (value) => `$${Number(value).toLocaleString("es-CL")}`;
  const formatLiters = (value) => `${Number(value).toLocaleString("es-CL")} L`;

  const palette = [
    "#0ea5e9",
    "#22c55e",
    "#f59e0b",
    "#6366f1",
    "#ef4444",
    "#14b8a6",
  ];

  const resolveDataPoints = (series, labels) => {
    const seriesMap = new Map(series.map((item) => [item.label, item.value]));
    return labels.map((label) => seriesMap.get(label) ?? 0);
  };

  const buildDatasetsFromMap = (seriesMap, labels) => {
    return Object.entries(seriesMap || {}).map(([label, series], index) => {
      const color = palette[index % palette.length];
      return {
        label,
        data: resolveDataPoints(series, labels),
        borderColor: color,
        backgroundColor: `${color}1a`,
        tension: 0.25,
        fill: false,
        pointRadius: 3,
        pointHoverRadius: 5,
      };
    });
  };

  profitData.forEach((branch, index) => {
    const canvas = document.getElementById(`profit-chart-${index}`);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const rangeSelector = document.querySelector(
      `select[data-branch-index="${index}"]`
    );
    const viewSelector = document.querySelector(
      `select[data-branch-view-index="${index}"]`
    );

    const seriesByRange = branch.series || {};
    const initialRange = seriesByRange.day || {};
    const labels = initialRange.labels || [];
    const datasets = [
      {
        label: "Ganancias",
        data: resolveDataPoints(initialRange.total || [], labels),
        borderColor: "#0ea5e9",
        backgroundColor: "rgba(14, 165, 233, 0.1)",
        tension: 0.25,
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 5,
      },
    ];

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: "index",
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: (value) => formatCurrency(value),
            },
          },
        },
      },
    });

    const updateChart = (range, view) => {
      const rangeData = seriesByRange[range] || {};
      const labels = rangeData.labels || [];

      let datasets = [];

      if (view === "fuels") {
        datasets = buildDatasetsFromMap(rangeData.fuels, labels);
      } else if (view === "products") {
        datasets = buildDatasetsFromMap(rangeData.products, labels);
      } else {
        datasets = [
          {
            label: "Ganancias",
            data: resolveDataPoints(rangeData.total || [], labels),
            borderColor: "#0ea5e9",
            backgroundColor: "rgba(14, 165, 233, 0.1)",
            tension: 0.25,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
        ];
      }

      chart.options.scales.y.ticks.callback =
        view === "fuels" ? formatLiters : formatCurrency;

      chart.data.labels = labels;
      chart.data.datasets = datasets;
      chart.update();
    };
    const handleUpdate = () => {
      const rangeValue = rangeSelector ? rangeSelector.value : "day";
      const viewValue = viewSelector ? viewSelector.value : "total";
      updateChart(rangeValue, viewValue);
    };


    if (rangeSelector) {
      rangeSelector.addEventListener("change", handleUpdate);
    }

    if (viewSelector) {
      viewSelector.addEventListener("change", handleUpdate);
    }

    handleUpdate();
  });
})();
