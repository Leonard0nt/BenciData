(function () {
  const profitDataElement = document.getElementById("profit-dashboard-data");
  if (!profitDataElement) return;

  const profitData = JSON.parse(profitDataElement.textContent);

  const buildDataset = (series) => {
    const labels = series.map((item) => item.label);
    const data = series.map((item) => item.value);
    return { labels, data };
  };

  profitData.forEach((branch, index) => {
    const canvas = document.getElementById(`profit-chart-${index}`);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const rangeSelector = document.querySelector(
      `select[data-branch-index="${index}"]`
    );

    const seriesByRange = branch.series || {};

    const initialSeries = seriesByRange.day || [];
    const { labels, data } = buildDataset(initialSeries);

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Ganancias",
            data,
            borderColor: "#0ea5e9",
            backgroundColor: "rgba(14, 165, 233, 0.1)",
            tension: 0.25,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
        ],
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
              callback: (value) => `$${value.toLocaleString("es-CL")}`,
            },
          },
        },
      },
    });

    const updateChart = (range) => {
      const selectedSeries = seriesByRange[range] || [];
      const nextData = buildDataset(selectedSeries);
      chart.data.labels = nextData.labels;
      chart.data.datasets[0].data = nextData.data;
      chart.update();
    };

    if (rangeSelector) {
      rangeSelector.addEventListener("change", (event) => {
        updateChart(event.target.value);
      });
      updateChart(rangeSelector.value);
    } else {
      updateChart("day");
    }
  });
})();
