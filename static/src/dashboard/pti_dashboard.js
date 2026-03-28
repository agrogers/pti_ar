/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";

// ── Colour palettes ──────────────────────────────────────────────────────────

const YEAR_COLORS = [
    "#4dc9f6", "#f67019", "#f53794", "#537bc4", "#acc236",
    "#166a8f", "#00a950", "#58595b", "#8549ba", "#e6194b",
    "#3cb44b", "#ffe119", "#4363d8",
];

const GENDER_COLORS = ["#36a2eb", "#ff6384", "#ffce56", "#9966ff"];

const DAY_COLORS = [
    "#4dc9f6",   // Monday
    "#f67019",   // Tuesday
    "#f53794",   // Wednesday
    "#537bc4",   // Thursday
    "#acc236",   // Friday
];

// ── Component ────────────────────────────────────────────────────────────────

export class PtiDashboard extends Component {
    static template = "pti_ar.PtiDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.doughnutRef = useRef("doughnutCanvas");
        this.barRef = useRef("barCanvas");

        this.state = useState({
            loading: true,
            cycleId: false,
            cycles: [],
            cards: {},
            doughnut: { year_level: {}, gender: {} },
            bar: { teachers: [], datasets: [] },
        });

        this._charts = [];

        onWillStart(async () => {
            // Chart.js is bundled with Odoo 18 — load it if not yet available
            if (!window.Chart) {
                try {
                    await loadJS("/web/static/lib/Chart/Chart.js");
                } catch {
                    // Odoo 18 may bundle chart.js differently
                }
            }
            await this._fetchData();
        });

        onMounted(() => {
            this._renderCharts();
        });

        onWillUnmount(() => {
            this._destroyCharts();
        });
    }

    // ── Data fetching ────────────────────────────────────────────────────────

    async _fetchData() {
        this.state.loading = true;
        const data = await this.orm.call(
            "pti.meeting.cycle",
            "get_dashboard_data",
            [this.state.cycleId || false],
        );
        Object.assign(this.state, {
            cycles: data.cycles || [],
            cards: data.cards || {},
            doughnut: data.doughnut || { year_level: {}, gender: {} },
            bar: data.bar || { teachers: [], datasets: [] },
            loading: false,
        });
    }

    async onCycleChange(ev) {
        const val = ev.target.value;
        this.state.cycleId = val ? parseInt(val, 10) : false;
        await this._fetchData();
        this._renderCharts();
    }

    // ── Chart rendering ──────────────────────────────────────────────────────

    _destroyCharts() {
        for (const c of this._charts) {
            c.destroy();
        }
        this._charts = [];
    }

    _renderCharts() {
        this._destroyCharts();

        const Chart = window.Chart;
        if (!Chart) {
            return;
        }

        this._renderDoughnut(Chart);
        this._renderBar(Chart);
    }

    _renderDoughnut(Chart) {
        const el = this.doughnutRef.el;
        if (!el) return;

        const yl = this.state.doughnut.year_level || {};
        const gd = this.state.doughnut.gender || {};

        const ylLabels = yl.labels || [];
        const ylData = yl.data || [];
        const gdLabels = gd.labels || [];
        const gdData = gd.data || [];

        const chart = new Chart(el, {
            type: "doughnut",
            data: {
                labels: [...ylLabels, ...gdLabels],
                datasets: [
                    {
                        label: "Year Level",
                        data: [...ylData, ...Array(gdLabels.length).fill(0)],
                        backgroundColor: YEAR_COLORS.slice(0, ylLabels.length).concat(
                            Array(gdLabels.length).fill("transparent")
                        ),
                        weight: 1,
                    },
                    {
                        label: "Gender",
                        data: [...Array(ylLabels.length).fill(0), ...gdData],
                        backgroundColor: Array(ylLabels.length)
                            .fill("transparent")
                            .concat(GENDER_COLORS.slice(0, gdLabels.length)),
                        weight: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "30%",
                plugins: {
                    legend: {
                        position: "right",
                        labels: {
                            generateLabels(chart) {
                                const yl_ds = chart.data.datasets[0];
                                const gd_ds = chart.data.datasets[1];
                                const labels = [];
                                for (let i = 0; i < ylLabels.length; i++) {
                                    labels.push({
                                        text: ylLabels[i],
                                        fillStyle: yl_ds.backgroundColor[i],
                                        strokeStyle: yl_ds.backgroundColor[i],
                                        hidden: false,
                                        index: i,
                                        datasetIndex: 0,
                                    });
                                }
                                for (let i = 0; i < gdLabels.length; i++) {
                                    labels.push({
                                        text: gdLabels[i],
                                        fillStyle: gd_ds.backgroundColor[ylLabels.length + i],
                                        strokeStyle: gd_ds.backgroundColor[ylLabels.length + i],
                                        hidden: false,
                                        index: ylLabels.length + i,
                                        datasetIndex: 1,
                                    });
                                }
                                return labels;
                            },
                        },
                    },
                    title: {
                        display: true,
                        text: "Meetings by Year Level (outer) & Gender (inner)",
                        font: { size: 14 },
                    },
                    tooltip: {
                        callbacks: {
                            label(ctx) {
                                const dsLabel = ctx.dataset.label;
                                const label = ctx.chart.data.labels[ctx.dataIndex];
                                const value = ctx.raw;
                                if (!value) return null;
                                return `${dsLabel}: ${label} — ${value}`;
                            },
                        },
                        filter(item) {
                            return item.raw > 0;
                        },
                    },
                },
            },
        });
        this._charts.push(chart);
    }

    _renderBar(Chart) {
        const el = this.barRef.el;
        if (!el) return;

        const barData = this.state.bar || {};
        const teachers = barData.teachers || [];
        const datasets = (barData.datasets || []).map((ds, idx) => ({
            label: ds.label,
            data: ds.data,
            backgroundColor: DAY_COLORS[idx % DAY_COLORS.length],
        }));

        const chart = new Chart(el, {
            type: "bar",
            data: {
                labels: teachers,
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        stacked: true,
                        title: { display: true, text: "Teacher" },
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        title: { display: true, text: "Number of Meetings" },
                        ticks: { stepSize: 1 },
                    },
                },
                plugins: {
                    title: {
                        display: true,
                        text: "Meetings per Teacher by Day of Week",
                        font: { size: 14 },
                    },
                    legend: { position: "top" },
                },
            },
        });
        this._charts.push(chart);
    }
}

registry.category("actions").add("pti_ar.dashboard", PtiDashboard);
