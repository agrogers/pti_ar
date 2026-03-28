/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";

/**
 * Generic search-dropdown component.
 *
 * Props:
 *   items       – Array of { id, name, detail? }  (the full list to filter)
 *   selectedId  – currently selected item id (or null)
 *   placeholder – input placeholder text
 *   noMatchText – text shown when search yields nothing
 *   onSelect    – callback(id)  when an item is picked
 *   onClear     – callback()    when the × button is clicked
 */
export class SearchDropdown extends Component {
    static template = "pti_ar.SearchDropdown";
    static props = {
        items: { type: Array },
        selectedId: { type: [Number, { value: null }], optional: true },
        placeholder: { type: String, optional: true },
        noMatchText: { type: String, optional: true },
        onSelect: Function,
        onClear: { type: Function, optional: true },
        onReady: { type: Function, optional: true },
    };
    static defaultProps = {
        placeholder: "Search\u2026",
        noMatchText: "No matches",
    };

    setup() {
        this.inputRef = useRef("ddInput");
        this.state = useState({
            search: "",
            open: false,
            highlightIndex: -1,
        });
        if (this.props.onReady) {
            this.props.onReady({ setValue: (text) => this.setValue(text) });
        }
    }

    get filtered() {
        const q = (this.state.search || "").trim().toLowerCase();
        if (!q) return this.props.items;
        return this.props.items.filter((i) => (i.name || "").toLowerCase().includes(q));
    }

    // --- Input events -------------------------------------------------------

    onInput(ev) {
        this.state.search = ev.target.value;
        this.state.open = true;
        this.state.highlightIndex = -1;
    }

    onFocus() {
        this.state.open = true;
    }

    onBlur() {
        setTimeout(() => {
            this.state.open = false;
            this.state.highlightIndex = -1;
        }, 200);
    }

    onKeydown(ev) {
        const items = this.filtered;
        if (!this.state.open || !items.length) {
            if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
                this.state.open = true;
                this.state.highlightIndex = 0;
                ev.preventDefault();
            }
            return;
        }
        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                this.state.highlightIndex = Math.min(this.state.highlightIndex + 1, items.length - 1);
                this._scrollIntoView();
                break;
            case "ArrowUp":
                ev.preventDefault();
                this.state.highlightIndex = Math.max(this.state.highlightIndex - 1, 0);
                this._scrollIntoView();
                break;
            case "Enter":
                ev.preventDefault();
                if (this.state.highlightIndex >= 0 && this.state.highlightIndex < items.length) {
                    this.pick(items[this.state.highlightIndex].id);
                }
                break;
            case "Escape":
                this.state.open = false;
                this.state.highlightIndex = -1;
                break;
        }
    }

    // --- Actions ------------------------------------------------------------

    pick(id) {
        const item = this.props.items.find((i) => i.id === id);
        this.state.search = item ? item.name : "";
        this.state.open = false;
        this.state.highlightIndex = -1;
        this.props.onSelect(id);
    }

    clear() {
        this.state.search = "";
        this.state.open = false;
        this.state.highlightIndex = -1;
        if (this.props.onClear) {
            this.props.onClear();
        }
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    /**
     * Set the visible search text externally (e.g. restoring a saved name).
     * Called by the parent via a ref on this component.
     */
    setValue(text) {
        this.state.search = text || "";
    }

    // --- Internal -----------------------------------------------------------

    _scrollIntoView() {
        requestAnimationFrame(() => {
            const el = this.inputRef.el
                ?.closest(".pti-sm-search-dropdown")
                ?.querySelector(".pti-sm-search-item.highlight");
            if (el) {
                el.scrollIntoView({ block: "nearest" });
            }
        });
    }
}
