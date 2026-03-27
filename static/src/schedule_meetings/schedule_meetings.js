/** @odoo-module **/

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getInitials(name) {
    if (!name) return "?";
    return name
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join("");
}

function storageGet(key, defaultVal) {
    try {
        const v = localStorage.getItem(key);
        if (v !== null) return JSON.parse(v);
    } catch (_) {}
    return defaultVal;
}

function storageSet(key, val) {
    try {
        localStorage.setItem(key, JSON.stringify(val));
    } catch (_) {}
}

// ---------------------------------------------------------------------------
// Notes Dialog (simple inline dialog built with OWL)
// ---------------------------------------------------------------------------

class MeetingDetailDialog extends Component {
    static template = "pti_ar.MeetingDetailDialog";
    static props = {
        meeting: Object,
        slotLabel: String,
        teacherName: String,
        onSaveNotes: Function,
        onDelete: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({
            notes: this.props.meeting.notes || "",
            confirmingDelete: false,
        });
    }

    getInitials(name) {
        return getInitials(name);
    }

    onSave() {
        this.props.onSaveNotes(this.props.meeting.id, this.state.notes);
    }

    onDeleteClick() {
        this.state.confirmingDelete = true;
    }

    onCancelDelete() {
        this.state.confirmingDelete = false;
    }

    onConfirmDelete() {
        this.props.onDelete(this.props.meeting.id);
    }
}

// ---------------------------------------------------------------------------
// Slot Detail Dialog (available / unavailable slots)
// ---------------------------------------------------------------------------

class SlotDetailDialog extends Component {
    static template = "pti_ar.SlotDetailDialog";
    static props = {
        status: String,
        slotLabel: String,
        teacherName: String,
        teacherId: Number,
        slotId: Number,
        onSetUnavailable: Function,
        onSetAvailable: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({
            selectedStatus: this.props.status,
        });
    }

    onStatusChange(ev) {
        this.state.selectedStatus = ev.target.value;
    }

    onSave() {
        if (this.state.selectedStatus === this.props.status) {
            this.props.onClose();
            return;
        }
        if (this.state.selectedStatus === 'unavailable') {
            this.props.onSetUnavailable(this.props.teacherId, this.props.slotId);
        } else {
            this.props.onSetAvailable(this.props.teacherId, this.props.slotId);
        }
    }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export class ScheduleMeetings extends Component {
    static template = "pti_ar.ScheduleMeetings";
    static components = { MeetingDetailDialog, SlotDetailDialog };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            parents: [],
            selectedParentId: null,
            parentData: null,
            // selectedTeachers: { [studentId]: [teacherId, ...] }
            selectedTeachers: {},
            slotData: null,
            loading: false,
            includeStudents: storageGet("pti_include_students", true),
            includeSpouse: storageGet("pti_include_spouse", false),
            meetingDetail: null, // { meeting, slotLabel, teacherName }
            slotDetail: null,    // { teacherId, slotId, slotLabel, teacherName, status, partnerSlotId }
            // Parent search dropdown
            parentSearch: "",
            parentDropdownOpen: false,
            parentHighlightIndex: -1,
        });

        this.parentInputRef = useRef("parentInput");

        onWillStart(async () => {
            await this._loadParents();
            // Restore last selected parent
            const savedId = storageGet("pti_selected_parent", null);
            if (savedId && this.state.parents.find((p) => p.id === savedId)) {
                await this.selectParent(savedId);
            }
        });
    }

    // -----------------------------------------------------------------------
    // Data loading
    // -----------------------------------------------------------------------

    async _loadParents() {
        this.state.loading = true;
        try {
            const parents = await this.orm.call("pti.schedule.meetings", "get_parents", []);
            this.state.parents = parents;
        } catch (e) {
            this._notify("Could not load parents: " + (e.message || e), "danger");
        } finally {
            this.state.loading = false;
        }
    }

    async _loadParentData(parentId) {
        this.state.loading = true;
        try {
            const data = await this.orm.call("pti.schedule.meetings", "get_parent_data", [parentId]);
            this.state.parentData = data;
        } catch (e) {
            this._notify("Could not load parent data: " + (e.message || e), "danger");
        } finally {
            this.state.loading = false;
        }
    }

    async _refreshSlotData() {
        const teacherIds = this._allSelectedTeacherIds();
        const parentId = this.state.selectedParentId;
        if (!teacherIds.length || !parentId) {
            this.state.slotData = null;
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call("pti.schedule.meetings", "get_slot_data", [
                teacherIds,
                parentId,
            ]);
            this.state.slotData = data;
        } catch (e) {
            this._notify("Could not load time slots: " + (e.message || e), "danger");
        } finally {
            this.state.loading = false;
        }
    }

    // -----------------------------------------------------------------------
    // Event handlers
    // -----------------------------------------------------------------------

    get filteredParents() {
        const q = (this.state.parentSearch || "").trim().toLowerCase();
        if (!q) return this.state.parents;
        return this.state.parents.filter((p) => (p.name || "").toLowerCase().includes(q));
    }

    onParentSearchInput(ev) {
        this.state.parentSearch = ev.target.value;
        this.state.parentDropdownOpen = true;
        this.state.parentHighlightIndex = -1;
    }

    onParentSearchFocus() {
        this.state.parentDropdownOpen = true;
    }

    onParentSearchBlur() {
        // Delay so click on dropdown item fires before close
        setTimeout(() => {
            this.state.parentDropdownOpen = false;
            this.state.parentHighlightIndex = -1;
        }, 200);
    }

    onParentSearchKeydown(ev) {
        const items = this.filteredParents;
        if (!this.state.parentDropdownOpen || !items.length) {
            if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
                this.state.parentDropdownOpen = true;
                this.state.parentHighlightIndex = 0;
                ev.preventDefault();
            }
            return;
        }
        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                this.state.parentHighlightIndex = Math.min(
                    this.state.parentHighlightIndex + 1,
                    items.length - 1
                );
                this._scrollHighlightedIntoView();
                break;
            case "ArrowUp":
                ev.preventDefault();
                this.state.parentHighlightIndex = Math.max(
                    this.state.parentHighlightIndex - 1,
                    0
                );
                this._scrollHighlightedIntoView();
                break;
            case "Enter":
                ev.preventDefault();
                if (this.state.parentHighlightIndex >= 0 && this.state.parentHighlightIndex < items.length) {
                    this.selectParent(items[this.state.parentHighlightIndex].id);
                }
                break;
            case "Escape":
                this.state.parentDropdownOpen = false;
                this.state.parentHighlightIndex = -1;
                break;
        }
    }

    _scrollHighlightedIntoView() {
        requestAnimationFrame(() => {
            const el = this.parentInputRef.el
                ?.closest(".pti-sm-search-dropdown")
                ?.querySelector(".pti-sm-search-item.highlight");
            if (el) {
                el.scrollIntoView({ block: "nearest" });
            }
        });
    }

    async selectParent(parentId) {
        this.state.selectedParentId = parentId;
        this.state.parentDropdownOpen = false;
        this.state.selectedTeachers = {};
        this.state.slotData = null;
        this.state.parentData = null;
        storageSet("pti_selected_parent", parentId);
        if (parentId) {
            const p = this.state.parents.find((x) => x.id === parentId);
            this.state.parentSearch = p ? p.name : "";
            await this._loadParentData(parentId);
            // Restore saved teacher selections for this parent
            const saved = storageGet("pti_teachers_" + parentId, null);
            if (saved && this.state.parentData) {
                // Validate: only keep teacher IDs that still exist for each student
                const validTeachers = {};
                for (const student of this.state.parentData.students) {
                    const validIds = student.teachers.map((t) => t.id);
                    const savedIds = saved[student.id] || [];
                    const filtered = savedIds.filter((id) => validIds.includes(id));
                    if (filtered.length) validTeachers[student.id] = filtered;
                }
                this.state.selectedTeachers = validTeachers;
                await this._refreshSlotData();
            }
        } else {
            this.state.parentSearch = "";
        }
    }

    clearParentSearch() {
        this.state.parentSearch = "";
        this.state.selectedParentId = null;
        this.state.parentDropdownOpen = false;
        this.state.selectedTeachers = {};
        this.state.slotData = null;
        this.state.parentData = null;
        storageSet("pti_selected_parent", null);
        if (this.parentInputRef.el) {
            this.parentInputRef.el.focus();
        }
    }

    async toggleTeacher(studentId, teacherId) {
        const current = this.state.selectedTeachers[studentId] || [];
        const idx = current.indexOf(teacherId);
        if (idx >= 0) {
            this.state.selectedTeachers[studentId] = current.filter((id) => id !== teacherId);
        } else {
            this.state.selectedTeachers[studentId] = [...current, teacherId];
        }
        this._saveTeacherSelections();
        await this._refreshSlotData();
    }

    _saveTeacherSelections() {
        const parentId = this.state.selectedParentId;
        if (!parentId) return;
        storageSet("pti_teachers_" + parentId, this.state.selectedTeachers);
    }

    onIncludeStudentsChange(ev) {
        this.state.includeStudents = ev.target.checked;
        storageSet("pti_include_students", this.state.includeStudents);
    }

    onIncludeSpouseChange(ev) {
        this.state.includeSpouse = ev.target.checked;
        storageSet("pti_include_spouse", this.state.includeSpouse);
    }

    // -----------------------------------------------------------------------
    // Booking
    // -----------------------------------------------------------------------

    async toggleStudent(studentId, teacherId, slotId) {
        const parentId = this.state.selectedParentId;
        if (!parentId) return;
        try {
            const result = await this.orm.call("pti.schedule.meetings", "toggle_student_on_meeting", [
                {
                    parent_id: parentId,
                    student_id: studentId,
                    teacher_id: teacherId,
                    slot_id: slotId,
                    include_students: this.state.includeStudents,
                    include_spouse: this.state.includeSpouse,
                },
            ]);
            const msgs = {
                created: "Meeting booked!",
                added: "Student added to meeting.",
                removed: "Student removed from meeting.",
                cancelled: "Meeting cancelled (no students).",
            };
            this._notify(msgs[result.action] || "Updated.", result.action === "cancelled" ? "warning" : "success");
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to update meeting.", "danger");
        }
    }

    // -----------------------------------------------------------------------
    // Meeting Detail Dialog
    // -----------------------------------------------------------------------

    openMeetingDetail(meeting, teacherName, slotLabel) {
        this.state.meetingDetail = { meeting, teacherName, slotLabel };
    }

    closeMeetingDetail() {
        this.state.meetingDetail = null;
    }

    openSlotInfoWithId(slotInfo, teacherId, slotId, teacherName, slotLabel) {
        this.state.slotDetail = {
            teacherId,
            slotId,
            slotLabel,
            teacherName,
            status: slotInfo.status,
            partnerSlotId: slotInfo.partnerSlotId,
        };
    }

    closeSlotInfo() {
        this.state.slotDetail = null;
    }

    /**
     * Unified handler for the Info button on every slot cell.
     * Opens the meeting detail dialog for booked slots, or the slot status
     * dialog (available/unavailable toggle) for unbooked slots.
     */
    openSlotDetail(slotInfo, col, slot) {
        const label = slot.date_display + ' ' + slot.start_display + ' – ' + slot.end_display;
        if (slotInfo.meeting) {
            this.openMeetingDetail(slotInfo.meeting, col.teacherName, label);
        } else {
            this.openSlotInfoWithId(slotInfo, col.teacherId, slot.id, col.teacherName, label);
        }
    }

    async setSlotUnavailable(teacherId, slotId) {
        try {
            const result = await this.orm.call("pti.schedule.meetings", "set_slot_unavailable", [teacherId, slotId]);
            if (result.cancelled_meeting) {
                this._notify("Slot marked unavailable. Existing meeting was cancelled.", "warning");
            } else {
                this._notify("Slot marked as unavailable.", "info");
            }
            this.state.slotDetail = null;
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to update slot.", "danger");
        }
    }

    async setSlotAvailable(teacherId, slotId) {
        try {
            await this.orm.call("pti.schedule.meetings", "set_slot_available", [teacherId, slotId]);
            this._notify("Slot marked as available.", "success");
            this.state.slotDetail = null;
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to update slot.", "danger");
        }
    }

    async saveNotes(meetingId, notes) {
        this.state.meetingDetail = null;
        try {
            await this.orm.call("pti.schedule.meetings", "save_meeting_notes", [meetingId, notes]);
            this._notify("Notes saved.", "success");
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to save notes.", "danger");
        }
    }

    async deleteMeeting(meetingId) {
        this.state.meetingDetail = null;
        try {
            await this.orm.call("pti.schedule.meetings", "cancel_meeting", [meetingId]);
            this._notify("Meeting cancelled.", "warning");
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to cancel meeting.", "danger");
        }
    }

    // -----------------------------------------------------------------------
    // Computed helpers used from the template
    // -----------------------------------------------------------------------

    isTeacherSelected(studentId, teacherId) {
        return (this.state.selectedTeachers[studentId] || []).includes(teacherId);
    }

    _allSelectedTeacherIds() {
        const ids = new Set();
        for (const arr of Object.values(this.state.selectedTeachers)) {
            for (const id of arr) {
                ids.add(id);
            }
        }
        return [...ids];
    }

    /**
     * Returns an array of objects:
     * { teacherId, teacherName, students: [{studentId, studentName, subject}] }
     * One entry per unique selected teacher.
     */
    getTeacherColumns() {
        if (!this.state.parentData) return [];

        // Map teacherId -> { name, students, studentKeys (Set for O(1) dedup) }
        const map = {};
        for (const student of this.state.parentData.students) {
            const selected = this.state.selectedTeachers[student.id] || [];
            for (const teacherId of selected) {
                const teacherInfo = student.teachers.find((t) => t.id === teacherId);
                if (!teacherInfo) continue;
                if (!map[teacherId]) {
                    map[teacherId] = {
                        teacherId,
                        teacherName: teacherInfo.name,
                        teacherImage: teacherInfo.image || null,
                        students: [],
                        _keys: new Set(),
                    };
                }
                const key = `${student.id}|${teacherInfo.subject}`;
                if (!map[teacherId]._keys.has(key)) {
                    map[teacherId]._keys.add(key);
                    map[teacherId].students.push({
                        studentId: student.id,
                        studentName: student.name,
                        subject: teacherInfo.subject,
                    });
                }
            }
        }
        // Strip internal _keys before returning
        return Object.values(map).map(({ _keys: _k, ...col }) => col);
    }

    /**
     * Returns the slot info for a given teacher + slot combo.
     * Returns { status, meeting, partnerSlotId } where status is
     * "available" | "booked_this" | "booked_other" | "unavailable"
     */
    getSlotInfo(teacherId, slotId) {
        if (!this.state.slotData) return { status: "available", meeting: null, partnerSlotId: null };
        const ts = this.state.slotData.teacher_slots[String(teacherId)];
        if (!ts) return { status: "available", meeting: null, partnerSlotId: null };
        const entry = ts[String(slotId)];
        if (!entry) return { status: "available", meeting: null, partnerSlotId: null };

        if (entry.status === "unavailable") {
            return { status: "unavailable", meeting: null, partnerSlotId: entry.partner_slot_id };
        }
        if (entry.status !== "booked" || !entry.meeting) {
            return { status: "available", meeting: null, partnerSlotId: entry.partner_slot_id };
        }
        const isParentMeeting = entry.meeting.is_parent_meeting;
        return {
            status: isParentMeeting ? "booked_this" : "booked_other",
            meeting: entry.meeting,
            partnerSlotId: entry.partner_slot_id,
        };
    }

    /**
     * True if a student has a booked meeting with a given teacher (from this parent).
     * Used to highlight the student-teacher checkbox row.
     */
    isStudentTeacherBooked(studentId, teacherId) {
        if (!this.state.slotData) return false;
        const ts = this.state.slotData.teacher_slots[String(teacherId)];
        if (!ts) return false;
        for (const entry of Object.values(ts)) {
            if (
                entry.status === "booked" &&
                entry.meeting &&
                entry.meeting.is_parent_meeting &&
                entry.meeting.connected_partner_ids.includes(studentId)
            ) {
                return true;
            }
        }
        return false;
    }

    /**
     * Students whose teacher selector is ticked for a particular column teacher.
     */
    getStudentsForTeacher(teacherId) {
        const students = [];
        if (!this.state.parentData) return students;
        for (const student of this.state.parentData.students) {
            if ((this.state.selectedTeachers[student.id] || []).includes(teacherId)) {
                students.push(student);
            }
        }
        return students;
    }

    getInitials(name) {
        return getInitials(name);
    }

    _notify(msg, type) {
        this.notification.add(msg, { type });
    }
}

registry.category("actions").add("pti_ar.schedule_meetings", ScheduleMeetings);
