document.addEventListener('DOMContentLoaded', function() {
    // 1. Monthly Revenue Chart
    const revCanvas = document.getElementById('revenueChart');
    if (revCanvas && window.Chart) {
        const labels = JSON.parse(revCanvas.dataset.labels || '[]');
        const data = JSON.parse(revCanvas.dataset.values || '[]');

        new Chart(revCanvas, {
            type: 'bar',
            data: {
                labels: labels.length ? labels : ['ខែមុន', 'ខែនេះ'],
                datasets: [{
                    label: 'ចំណូលសរុប (រៀល - KHR)',
                    data: data.length ? data : [0, 0],
                    backgroundColor: 'rgba(14, 165, 233, 0.75)',
                    borderColor: '#0284c7',
                    borderWidth: 2,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.raw.toLocaleString() + ' ៛';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#f1f5f9' },
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString() + ' ៛';
                            }
                        }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 2. Consumption by Customer Type Chart (Doughnut)
    const typeCanvas = document.getElementById('typeConsumptionChart');
    if (typeCanvas && window.Chart) {
        const resVal = parseFloat(typeCanvas.dataset.res || 0);
        const comVal = parseFloat(typeCanvas.dataset.com || 0);
        const indVal = parseFloat(typeCanvas.dataset.ind || 0);

        new Chart(typeCanvas, {
            type: 'doughnut',
            data: {
                labels: ['លំនៅឋាន (Residential)', 'អាជីវកម្ម (Commercial)', 'ឧស្សាហកម្ម (Industrial)'],
                datasets: [{
                    data: [resVal, comVal, indVal],
                    backgroundColor: ['#0284c7', '#8b5cf6', '#f59e0b'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            font: { family: 'Kantumruy Pro', size: 12 },
                            boxWidth: 14,
                            padding: 14
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.raw.toLocaleString()} kWh`;
                            }
                        }
                    }
                },
                cutout: '70%'
            }
        });
    }
});
