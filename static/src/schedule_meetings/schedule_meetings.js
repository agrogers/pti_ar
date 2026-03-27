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

class NotesDialog extends Component {
    static template = "pti_ar.NotesDialog";
    static props = {
        meetingId: Number,
        notes: String,
        onSave: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({ notes: this.props.notes });
    }

    onSave() {
        this.props.onSave(this.props.meetingId, this.state.notes);
    }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export class ScheduleMeetings extends Component {
    static template = "pti_ar.ScheduleMeetings";
    static components = { NotesDialog };

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
            notesDialog: null, // { meetingId, notes }
            cancelConfirm: null, // { meetingId, teacherName, slotLabel }
        });

        onWillStart(async () => {
            await this._loadParents();
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

    async onParentChange(ev) {
        const val = ev.target.value;
        const parentId = val ? parseInt(val) : null;
        this.state.selectedParentId = parentId;
        this.state.selectedTeachers = {};
        this.state.slotData = null;
        this.state.parentData = null;
        if (parentId) {
            await this._loadParentData(parentId);
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
        await this._refreshSlotData();
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

    async bookSlot(studentIds, teacherId, slotId) {
        const parentId = this.state.selectedParentId;
        if (!parentId) return;
        try {
            await this.orm.call("pti.schedule.meetings", "book_meeting", [
                {
                    parent_id: parentId,
                    student_ids: studentIds,
                    teacher_id: teacherId,
                    slot_id: slotId,
                    include_students: this.state.includeStudents,
                    include_spouse: this.state.includeSpouse,
                },
            ]);
            this._notify("Meeting booked successfully!", "success");
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to book meeting.", "danger");
        }
    }

    requestCancel(meetingId, teacherName, slotLabel) {
        this.state.cancelConfirm = { meetingId, teacherName, slotLabel };
    }

    dismissCancel() {
        this.state.cancelConfirm = null;
    }

    async confirmCancel() {
        const { meetingId } = this.state.cancelConfirm;
        this.state.cancelConfirm = null;
        try {
            await this.orm.call("pti.schedule.meetings", "cancel_meeting", [meetingId]);
            this._notify("Meeting cancelled.", "warning");
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to cancel meeting.", "danger");
        }
    }

    // -----------------------------------------------------------------------
    // Notes
    // -----------------------------------------------------------------------

    openNotes(meetingId, notes) {
        this.state.notesDialog = { meetingId, notes: notes || "" };
    }

    closeNotes() {
        this.state.notesDialog = null;
    }

    async saveNotes(meetingId, notes) {
        this.state.notesDialog = null;
        try {
            await this.orm.call("pti.schedule.meetings", "save_meeting_notes", [meetingId, notes]);
            this._notify("Notes saved.", "success");
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to save notes.", "danger");
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
     * Returns { status, meeting } where status is "available" | "booked_this" | "booked_other"
     */
    getSlotInfo(teacherId, slotId) {
        if (!this.state.slotData) return { status: "available", meeting: null };
        const ts = this.state.slotData.teacher_slots[String(teacherId)];
        if (!ts) return { status: "available", meeting: null };
        const entry = ts[String(slotId)];
        if (!entry) return { status: "available", meeting: null };

        if (entry.status !== "booked" || !entry.meeting) {
            return { status: "available", meeting: null };
        }
        const isParentMeeting = entry.meeting.is_parent_meeting;
        return {
            status: isParentMeeting ? "booked_this" : "booked_other",
            meeting: entry.meeting,
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
