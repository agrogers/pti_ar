/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { SearchDropdown } from "../components/search_dropdown";

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
// Unified Slot / Meeting Dialog
// ---------------------------------------------------------------------------

class SlotDialog extends Component {
    static template = "pti_ar.SlotDialog";
    static props = {
        slotLabel: String,
        teacherName: String,
        teacherId: Number,
        slotId: Number,
        status: String,
        slotState: { type: String, optional: true },
        meeting: { type: [Object, { value: null }], optional: true },
        onSaveMeeting: Function,
        onSetUnavailable: Function,
        onSetAvailable: Function,
        onDeleteMeeting: Function,
        onClose: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.dialogService = useService("dialog");

        const m = this.props.meeting;
        this.state = useState({
            selectedStatus: this.props.status === "unavailable" ? "unavailable" : "available",
            connectedStudents: m
                ? (m.connected_partners || []).map((p) => ({ id: p.id, name: p.name }))
                : [],
            members: m ? (m.members || []).map((mem) => ({ ...mem })) : [],
            notes: m ? m.notes || "" : "",
            confirmingDelete: false,
        });
    }

    getInitials(name) {
        return getInitials(name);
    }

    get isBooked() {
        return !!this.props.meeting;
    }

    get isSlotUnavailable() {
        return this.props.slotState === "unavailable";
    }

    get hasPeople() {
        return this.state.connectedStudents.length > 0 || this.state.members.length > 0;
    }

    get showPeopleSection() {
        if (this.isSlotUnavailable) return false;
        return this.isBooked || this.state.selectedStatus !== "unavailable";
    }

    get teacherMembers() {
        return this.state.members.filter((m) => m.is_teacher);
    }
    get parentMembers() {
        return this.state.members.filter((m) => m.is_parent);
    }
    get observerMembers() {
        return this.state.members.filter((m) => m.is_observer);
    }

    // -- Availability --------------------------------------------------------

    onStatusChange(ev) {
        this.state.selectedStatus = ev.target.value;
    }

    // -- Add people via Odoo search dialog -----------------------------------

    _openPartnerSearch(title, extraDomain, onDone) {
        const allUsed = [
            ...this.state.connectedStudents.map((s) => s.id),
            ...this.state.members.map((m) => m.partner_id),
        ];
        const domain = [["id", "not in", allUsed], ...(extraDomain || [])];
        this.dialogService.add(SelectCreateDialog, {
            resModel: "res.partner",
            title,
            domain,
            multiSelect: true,
            noCreate: true,
            onSelected: async (resIds) => {
                const partners = await this.orm.call("res.partner", "read", [
                    resIds,
                    ["name", "customer_name"],
                ]);
                onDone(
                    partners.map((p) => ({
                        id: p.id,
                        name: p.customer_name || p.name,
                    }))
                );
            },
        });
    }

    addConnectedStudent() {
        this._openPartnerSearch("Add Connected Student", [], (partners) => {
            for (const p of partners) {
                if (!this.state.connectedStudents.find((s) => s.id === p.id)) {
                    this.state.connectedStudents.push({ id: p.id, name: p.name });
                }
            }
        });
    }

    removeConnectedStudent(id) {
        this.state.connectedStudents = this.state.connectedStudents.filter(
            (s) => s.id !== id
        );
    }

    addMember(role) {
        const titles = { teacher: "Add Teacher", parent: "Add Parent", observer: "Add Observer" };
        this._openPartnerSearch(titles[role] || "Add Member", [], (partners) => {
            for (const p of partners) {
                this.state.members.push({
                    partner_id: p.id,
                    partner_name: p.name,
                    is_teacher: role === "teacher",
                    is_parent: role === "parent",
                    is_student: false,
                    is_observer: role === "observer",
                });
            }
        });
    }

    removeMember(partnerId, role) {
        this.state.members = this.state.members.filter((m) => {
            if (m.partner_id !== partnerId) return true;
            if (role === "teacher") return !m.is_teacher;
            if (role === "parent") return !m.is_parent;
            if (role === "observer") return !m.is_observer;
            return true;
        });
    }

    // -- Delete --------------------------------------------------------------

    onDeleteClick() {
        this.state.confirmingDelete = true;
    }
    onCancelDelete() {
        this.state.confirmingDelete = false;
    }
    onConfirmDelete() {
        this.props.onDeleteMeeting(this.props.meeting.id);
    }

    // -- Save ----------------------------------------------------------------

    onSave() {
        // No meeting and no people → availability change only
        if (!this.isBooked && !this.hasPeople) {
            const origStatus = this.props.status === "unavailable" ? "unavailable" : "available";
            if (this.state.selectedStatus !== origStatus) {
                if (this.state.selectedStatus === "unavailable") {
                    this.props.onSetUnavailable(this.props.teacherId, this.props.slotId);
                } else {
                    this.props.onSetAvailable(this.props.teacherId, this.props.slotId);
                }
            } else {
                this.props.onClose();
            }
            return;
        }

        // Create or update meeting
        this.props.onSaveMeeting({
            teacher_id: this.props.teacherId,
            slot_id: this.props.slotId,
            meeting_id: this.isBooked ? this.props.meeting.id : false,
            connected_student_ids: this.state.connectedStudents.map((s) => s.id),
            members: this.state.members.map((m) => ({
                partner_id: m.partner_id,
                is_teacher: m.is_teacher || false,
                is_parent: m.is_parent || false,
                is_student: m.is_student || false,
                is_observer: m.is_observer || false,
            })),
            notes: this.state.notes,
        });
    }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export class ScheduleMeetings extends Component {
    static template = "pti_ar.ScheduleMeetings";
    static components = { SlotDialog, SearchDropdown };
    static props = {
        action: { type: Object, optional: true },
        breadcrumbs: { type: Array, optional: true },
        actionId: { type: [Number, String, Boolean], optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            // View mode: "parent" | "teacher" | "student"
            mode: storageGet("pti_mode", "parent"),

            // Parent mode state
            parents: [],
            selectedParentId: null,
            parentData: null,

            // Teacher mode state
            teachers: [],
            selectedTeacherId: null,
            teacherData: null,  // { students: [{id, name, image, classes, parent_id}], teacher_id }
            selectedStudentIds: [],  // student partner IDs ticked for scheduling
            teacherStudentMode: storageGet("pti_teacher_student_mode", "all"),  // "all" | "single"
            selectedSingleStudentId: null,

            // selectedTeachers: { [studentId]: [teacherId, ...] }
            selectedTeachers: {},
            selectedSubjects: {},  // { [studentId]: { [teacherId]: [subjectStr, ...] } }
            slotData: null,
            loading: false,
            includeStudents: storageGet("pti_include_students", true),
            includeSpouse: storageGet("pti_include_spouse", false),
            teacherListDisplay: storageGet("pti_teacher_list_display", "teacher"),  // "teacher" | "subject"
            slotDialog: null,   // { teacherId, slotId, slotLabel, teacherName, status, meeting }
        });

        this._mainDropdownApi = null;
        this._studentDropdownApi = null;

        onWillStart(async () => {
            if (this.state.mode === "teacher") {
                await this._loadTeachers();
                const savedId = storageGet("pti_selected_teacher", null);
                if (savedId && this.state.teachers.find((t) => t.id === savedId)) {
                    await this.selectTeacher(savedId);
                }
            } else {
                await this._loadParents();
                const savedId = storageGet("pti_selected_parent", null);
                if (savedId && this.state.parents.find((p) => p.id === savedId)) {
                    await this.selectParent(savedId);
                }
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

    async _loadTeachers() {
        this.state.loading = true;
        try {
            const teachers = await this.orm.call("pti.schedule.meetings", "get_teachers", []);
            this.state.teachers = teachers;
        } catch (e) {
            this._notify("Could not load teachers: " + (e.message || e), "danger");
        } finally {
            this.state.loading = false;
        }
    }

    async _loadTeacherData(teacherId) {
        this.state.loading = true;
        try {
            const data = await this.orm.call("pti.schedule.meetings", "get_teacher_data", [teacherId]);
            this.state.teacherData = data;
        } catch (e) {
            this._notify("Could not load teacher data: " + (e.message || e), "danger");
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
        let teacherIds, parentId;
        if (this.state.mode === "teacher") {
            teacherIds = this.state.selectedTeacherId ? [this.state.selectedTeacherId] : [];
            // For teacher mode, we need a parent_id for get_slot_data.
            // Use the first selected student's parent or 0 (will show all as booked_other).
            parentId = this._getTeacherModeParentId();
        } else {
            teacherIds = this._allSelectedTeacherIds();
            parentId = this.state.selectedParentId;
        }
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

    // -----------------------------------------------------------------------
    // Mode switching
    // -----------------------------------------------------------------------

    async setMode(mode) {
        if (mode === this.state.mode) return;
        // Reset state
        this.state.mode = mode;
        this.state.selectedParentId = null;
        this.state.parentData = null;
        this.state.selectedTeacherId = null;
        this.state.teacherData = null;
        this.state.selectedStudentIds = [];
        this.state.selectedSingleStudentId = null;
        this.state.selectedTeachers = {};
        this.state.slotData = null;
        this.state.slotDialog = null;
        storageSet("pti_mode", mode);

        if (mode === "teacher") {
            await this._loadTeachers();
            const savedId = storageGet("pti_selected_teacher", null);
            if (savedId && this.state.teachers.find((t) => t.id === savedId)) {
                await this.selectTeacher(savedId);
            }
        } else {
            await this._loadParents();
            const savedId = storageGet("pti_selected_parent", null);
            if (savedId && this.state.parents.find((p) => p.id === savedId)) {
                await this.selectParent(savedId);
            }
        }
    }

    // -----------------------------------------------------------------------
    // Main dropdown computed props  (parent or teacher list)
    // -----------------------------------------------------------------------

    get mainDropdownItems() {
        if (this.state.mode === "teacher") {
            return this.state.teachers.map((t) => ({
                id: t.id,
                name: t.name,
                detail: "(" + t.student_count + " students)",
            }));
        }
        return this.state.parents.map((p) => ({
            id: p.id,
            name: p.name,
            detail: "(" + p.child_count + (p.child_count === 1 ? " child" : " children") + ")",
        }));
    }

    get mainDropdownSelectedId() {
        return this.state.mode === "teacher"
            ? this.state.selectedTeacherId
            : this.state.selectedParentId;
    }

    get mainDropdownPlaceholder() {
        return this.state.mode === "teacher" ? "Search teacher\u2026" : "Search parent\u2026";
    }

    get mainDropdownNoMatch() {
        return this.state.mode === "teacher" ? "No matching teachers" : "No matching parents";
    }

    onMainDropdownSelect(id) {
        if (this.state.mode === "teacher") {
            this.selectTeacher(id);
        } else {
            this.selectParent(id);
        }
    }

    onMainDropdownClear() {
        this.state.slotData = null;
        if (this.state.mode === "teacher") {
            this.state.selectedTeacherId = null;
            this.state.teacherData = null;
            this.state.selectedStudentIds = [];
            this.state.selectedSingleStudentId = null;
            storageSet("pti_selected_teacher", null);
        } else {
            this.state.selectedParentId = null;
            this.state.parentData = null;
            this.state.selectedTeachers = {};
            storageSet("pti_selected_parent", null);
        }
    }

    // -----------------------------------------------------------------------
    // Student dropdown computed props  (single-student mode)
    // -----------------------------------------------------------------------

    get studentDropdownItems() {
        if (!this.state.teacherData) return [];
        return this.state.teacherData.students.map((s) => ({
            id: s.id,
            name: s.name,
            detail: s.classes.length
                ? "(" + s.classes.map((c) => c.class_code).join(", ") + ")"
                : "",
        }));
    }

    onStudentDropdownSelect(id) {
        this.selectSingleStudent(id);
    }

    onStudentDropdownClear() {
        this.state.selectedSingleStudentId = null;
        if (this.state.selectedTeacherId) {
            storageSet("pti_teacher_single_student_" + this.state.selectedTeacherId, null);
        }
        this._buildTeacherModeTeacherSelections();
    }

    async selectParent(parentId) {
        this.state.selectedParentId = parentId;
        this.state.selectedTeachers = {};
        this.state.selectedSubjects = {};
        this.state.slotData = null;
        this.state.parentData = null;
        storageSet("pti_selected_parent", parentId);
        if (parentId) {
            const p = this.state.parents.find((x) => x.id === parentId);
            this._setMainDropdownText(p ? p.name : "");
            await this._loadParentData(parentId);
            // Restore saved teacher selections for this parent
            const saved = storageGet("pti_teachers_" + parentId, null);
            const savedSubjects = storageGet("pti_subjects_" + parentId, null);
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
                if (savedSubjects) {
                    this.state.selectedSubjects = savedSubjects;
                }
                await this._refreshSlotData();
            }
        } else {
            this._setMainDropdownText("");
        }
    }

    clearParentSearch() {
        this.state.slotData = null;
        if (this.state.mode === "teacher") {
            this.state.selectedTeacherId = null;
            this.state.teacherData = null;
            this.state.selectedStudentIds = [];
            this.state.selectedSingleStudentId = null;
            storageSet("pti_selected_teacher", null);
        } else {
            this.state.selectedParentId = null;
            this.state.parentData = null;
            this.state.selectedTeachers = {};
            this.state.selectedSubjects = {};
            storageSet("pti_selected_parent", null);
        }
    }

    // -----------------------------------------------------------------------
    // Teacher mode selection
    // -----------------------------------------------------------------------

    async selectTeacher(teacherId) {
        this.state.selectedTeacherId = teacherId;
        this.state.selectedStudentIds = [];
        this.state.selectedTeachers = {};
        this.state.slotData = null;
        this.state.teacherData = null;
        this.state.selectedSingleStudentId = null;
        storageSet("pti_selected_teacher", teacherId);
        if (teacherId) {
            const t = this.state.teachers.find((x) => x.id === teacherId);
            this._setMainDropdownText(t ? t.name : "");
            await this._loadTeacherData(teacherId);
            if (this.state.teacherData) {
                // Auto-select all students so slots load immediately
                this.state.selectedStudentIds = this.state.teacherData.students.map((s) => s.id);
                // Restore single student selection if applicable
                const savedSingleId = storageGet(
                    "pti_teacher_single_student_" + teacherId, null
                );
                if (savedSingleId && this.state.teacherData.students.find((s) => s.id === savedSingleId)) {
                    this.state.selectedSingleStudentId = savedSingleId;
                    const st = this.state.teacherData.students.find((s) => s.id === savedSingleId);
                    this._setStudentDropdownText(st ? this.getStudentOptionLabel(st) : "");
                }
                this._buildTeacherModeTeacherSelections();
                await this._refreshSlotData();
            }
        } else {
            this._setMainDropdownText("");
        }
    }

    async toggleStudentSelection(studentId) {
        const idx = this.state.selectedStudentIds.indexOf(studentId);
        if (idx >= 0) {
            this.state.selectedStudentIds = this.state.selectedStudentIds.filter((id) => id !== studentId);
        } else {
            this.state.selectedStudentIds = [...this.state.selectedStudentIds, studentId];
        }
        this._saveTeacherStudentSelections();
        this._buildTeacherModeTeacherSelections();
        await this._refreshSlotData();
    }

    _saveTeacherStudentSelections() {
        const teacherId = this.state.selectedTeacherId;
        if (!teacherId) return;
        storageSet("pti_teacher_students_" + teacherId, this.state.selectedStudentIds);
    }

    setTeacherStudentMode(mode) {
        this.state.teacherStudentMode = mode;
        storageSet("pti_teacher_student_mode", mode);
        this._buildTeacherModeTeacherSelections();
    }

    selectSingleStudent(studentId) {
        this.state.selectedSingleStudentId = studentId;
        if (this.state.selectedTeacherId) {
            storageSet("pti_teacher_single_student_" + this.state.selectedTeacherId, studentId);
        }
        this._buildTeacherModeTeacherSelections();
    }

    _getTeacherModeEffectiveStudentIds() {
        if (!this.state.teacherData) return [];
        if (this.state.teacherStudentMode === "single") {
            return this.state.selectedSingleStudentId ? [this.state.selectedSingleStudentId] : [];
        }
        return this.state.teacherData.students.map((s) => s.id);
    }

    /**
     * In teacher mode, build parentData-compatible structure so the grid
     * template can render the same way. Each selected student gets the
     * single teacher column.
     */
    _buildTeacherModeTeacherSelections() {
        const teacherId = this.state.selectedTeacherId;
        if (!teacherId || !this.state.teacherData) return;
        const sel = {};
        for (const sid of this._getTeacherModeEffectiveStudentIds()) {
            sel[sid] = [teacherId];
        }
        this.state.selectedTeachers = sel;
    }

    /**
     * Get the parent_id to use for slot data loading in teacher mode.
     * Returns first selected student's parent, or 0.
     */
    _getTeacherModeParentId() {
        if (!this.state.teacherData?.students?.length) return 0;
        for (const st of this.state.teacherData.students) {
            if (st.parent_id) return st.parent_id;
        }
        return 0;
    }

    isStudentSelected(studentId) {
        return this.state.selectedStudentIds.includes(studentId);
    }

    async toggleTeacher(studentId, teacherId) {
        const current = this.state.selectedTeachers[studentId] || [];
        const idx = current.indexOf(teacherId);
        if (idx >= 0) {
            this.state.selectedTeachers[studentId] = current.filter((id) => id !== teacherId);
            // Clear subject selections for this teacher
            if (this.state.selectedSubjects[studentId]) {
                delete this.state.selectedSubjects[studentId][teacherId];
            }
        } else {
            this.state.selectedTeachers[studentId] = [...current, teacherId];
            // Select all subjects for this teacher
            if (!this.state.selectedSubjects[studentId]) {
                this.state.selectedSubjects[studentId] = {};
            }
            this.state.selectedSubjects[studentId][teacherId] = this._getTeacherSubjects(studentId, teacherId);
        }
        this._saveTeacherSelections();
        this._saveSubjectSelections();
        await this._refreshSlotData();
    }

    async toggleSubjectEntry(studentId, teacherId, subject) {
        if (!this.state.selectedSubjects[studentId]) {
            this.state.selectedSubjects[studentId] = {};
        }
        const current = this.state.selectedSubjects[studentId][teacherId] || [];
        const idx = current.indexOf(subject);
        if (idx >= 0) {
            this.state.selectedSubjects[studentId][teacherId] = current.filter((s) => s !== subject);
        } else {
            this.state.selectedSubjects[studentId][teacherId] = [...current, subject];
        }
        // Sync teacher selection: selected if any subjects remain
        const remaining = this.state.selectedSubjects[studentId][teacherId];
        const teacherList = this.state.selectedTeachers[studentId] || [];
        const teacherSelected = teacherList.includes(teacherId);
        if (remaining.length > 0 && !teacherSelected) {
            this.state.selectedTeachers[studentId] = [...teacherList, teacherId];
        } else if (remaining.length === 0 && teacherSelected) {
            this.state.selectedTeachers[studentId] = teacherList.filter((id) => id !== teacherId);
        }
        this._saveTeacherSelections();
        this._saveSubjectSelections();
        await this._refreshSlotData();
    }

    isSubjectSelected(studentId, teacherId, subject) {
        return (this.state.selectedSubjects[studentId]?.[teacherId] || []).includes(subject);
    }

    _saveTeacherSelections() {
        const parentId = this.state.selectedParentId;
        if (!parentId) return;
        storageSet("pti_teachers_" + parentId, this.state.selectedTeachers);
    }

    _saveSubjectSelections() {
        const parentId = this.state.selectedParentId;
        if (!parentId) return;
        storageSet("pti_subjects_" + parentId, this.state.selectedSubjects);
    }

    onIncludeStudentsChange(ev) {
        this.state.includeStudents = ev.target.checked;
        storageSet("pti_include_students", this.state.includeStudents);
    }

    onIncludeSpouseChange(ev) {
        this.state.includeSpouse = ev.target.checked;
        storageSet("pti_include_spouse", this.state.includeSpouse);
    }

    setTeacherListDisplay(mode) {
        this.state.teacherListDisplay = mode;
        storageSet("pti_teacher_list_display", mode);
    }

    /**
     * Return label parts for a teacher entry (used in "By Teacher" mode).
     * @returns {{ primary: string, secondary: string }}
     */
    getTeacherLabel(teacher) {
        return { primary: teacher.name, secondary: teacher.subject };
    }

    /**
     * Flatten student.teachers into one entry per subject, sorted alphabetically.
     * Used in "By Subject" display mode.
     * @returns {Array<{teacherId: number, subject: string, teacherLabel: string, is_assistant: boolean}>}
     */
    getSubjectList(student) {
        const entries = [];
        for (const teacher of student.teachers) {
            const subjects = teacher.subject
                ? teacher.subject.split(", ").map((s) => s.trim()).filter(Boolean)
                : [""];
            const label = teacher.code || teacher.name;
            for (const subj of subjects) {
                entries.push({
                    teacherId: teacher.id,
                    subject: subj,
                    teacherLabel: label,
                    is_assistant: teacher.is_assistant,
                });
            }
        }
        entries.sort((a, b) => a.subject.localeCompare(b.subject));
        return entries;
    }

    /**
     * Get all subject codes for a teacher+student from parentData.
     */
    _getTeacherSubjects(studentId, teacherId) {
        const students = this.state.parentData?.students || [];
        const student = students.find((s) => s.id === studentId);
        if (!student) return [];
        const teacher = student.teachers.find((t) => t.id === teacherId);
        if (!teacher || !teacher.subject) return [];
        return teacher.subject.split(", ").map((s) => s.trim()).filter(Boolean);
    }

    /**
     * Build meeting note text based on display mode and selected subjects.
     */
    _buildMeetingNote(studentId, teacherId) {
        if (this.state.mode !== "parent") return "";
        if (this.state.teacherListDisplay === "subject") {
            const subjects = this.state.selectedSubjects[studentId]?.[teacherId] || [];
            return subjects.length ? "Related subjects: " + subjects.join(", ") : "";
        }
        const subjects = this._getTeacherSubjects(studentId, teacherId);
        return subjects.length ? "Teacher subjects: " + subjects.join(", ") : "";
    }

    // -----------------------------------------------------------------------
    // Booking
    // -----------------------------------------------------------------------

    async toggleStudent(studentId, teacherId, slotId) {
        let parentId;
        if (this.state.mode === "teacher") {
            // Resolve parent from student's teacherData entry
            const st = this.state.teacherData?.students.find((s) => s.id === studentId);
            parentId = st?.parent_id;
            if (!parentId) {
                this._notify("No parent found for this student.", "danger");
                return;
            }
        } else {
            parentId = this.state.selectedParentId;
        }
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
                    notes: this._buildMeetingNote(studentId, teacherId),
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

    /**
     * Open the unified slot / meeting dialog for any slot cell.
     */
    openSlotDialog(slotInfo, col, slot) {
        const label = slot.date_display + ' ' + slot.start_display + ' – ' + slot.end_display;
        this.state.slotDialog = {
            teacherId: col.teacherId,
            slotId: slot.id,
            slotLabel: label,
            teacherName: col.teacherName,
            status: slotInfo.status || "available",            slotState: slot.state || "available",            meeting: slotInfo.meeting || null,
        };
    }

    closeSlotDialog() {
        this.state.slotDialog = null;
    }

    async setSlotUnavailable(teacherId, slotId) {
        try {
            const result = await this.orm.call("pti.schedule.meetings", "set_slot_unavailable", [teacherId, slotId]);
            if (result.cancelled_meeting) {
                this._notify("Slot marked unavailable. Existing meeting was cancelled.", "warning");
            } else {
                this._notify("Slot marked as unavailable.", "info");
            }
            this.state.slotDialog = null;
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to update slot.", "danger");
        }
    }

    async setSlotAvailable(teacherId, slotId) {
        try {
            await this.orm.call("pti.schedule.meetings", "set_slot_available", [teacherId, slotId]);
            this._notify("Slot marked as available.", "success");
            this.state.slotDialog = null;
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to update slot.", "danger");
        }
    }

    async saveMeeting(params) {
        this.state.slotDialog = null;
        try {
            await this.orm.call("pti.schedule.meetings", "save_slot_meeting", [params]);
            this._notify(params.meeting_id ? "Meeting updated." : "Meeting booked.", "success");
            await this._refreshSlotData();
        } catch (e) {
            this._notify(e.data?.message || e.message || "Failed to save meeting.", "danger");
        }
    }

    async deleteMeeting(meetingId) {
        this.state.slotDialog = null;
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
    /**
     * Returns parentData-like student list. In teacher mode, returns
     * teacherData.students shaped like parentData.students (with a
     * synthetic teachers array so the grid renders correctly).
     */
    getEffectiveStudents() {
        if (this.state.mode === "teacher") {
            if (!this.state.teacherData) return [];
            const teacherId = this.state.selectedTeacherId;
            const teacher = this.state.teachers.find((t) => t.id === teacherId);
            const teacherName = teacher ? teacher.name : "";
            let students = this.state.teacherData.students;
            if (this.state.teacherStudentMode === "single") {
                students = this.state.selectedSingleStudentId
                    ? students.filter((s) => s.id === this.state.selectedSingleStudentId)
                    : [];
            }
            return students.map((s) => ({
                ...s,
                teachers: [{
                    id: teacherId,
                    name: teacherName,
                    subject: s.classes.map((c) => c.class_code).join(", "),
                    is_assistant: false,
                    class_id: s.classes.length ? s.classes[0].class_id : null,
                    image: null,
                }],
            }));
        }
        return this.state.parentData ? this.state.parentData.students : [];
    }

    getTeacherColumns() {
        // In teacher mode, always show the single teacher column
        if (this.state.mode === "teacher" && this.state.selectedTeacherId && this.state.teacherData) {
            const teacher = this.state.teachers.find((t) => t.id === this.state.selectedTeacherId);
            const effective = this.getEffectiveStudents();
            return [{
                teacherId: this.state.selectedTeacherId,
                teacherName: teacher ? teacher.name : "",
                teacherImage: teacher ? teacher.image || null : null,
                students: effective.map((s) => ({
                    studentId: s.id,
                    studentName: s.name,
                    subject: s.classes ? s.classes.map((c) => c.class_code).join(", ") : "",
                })),
            }];
        }

        const students = this.getEffectiveStudents();
        if (!students.length) return [];

        // Map teacherId -> { name, students, studentKeys (Set for O(1) dedup) }
        const map = {};
        for (const student of students) {
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

        // Check global slot state first (applies to ALL teachers)
        const slotObj = this.state.slotData.time_slots.find((s) => s.id === slotId);
        if (slotObj && slotObj.state === "unavailable") {
            return { status: "slot_unavailable", meeting: null, partnerSlotId: null };
        }

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
        // In teacher mode, all booked slots are "ours" — the teacher is the focus
        const status = (this.state.mode === "teacher" || isParentMeeting) ? "booked_this" : "booked_other";
        return {
            status,
            meeting: entry.meeting,
            partnerSlotId: entry.partner_slot_id,
        };
    }

    /**
     * True if slotId is in the conflict list (parent has 2+ teachers booked at the same time).
     */
    isConflictSlot(slotId) {
        if (!this.state.slotData || !this.state.slotData.conflict_slot_ids) return false;
        return this.state.slotData.conflict_slot_ids.includes(slotId);
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
                entry.meeting.connected_partner_ids.includes(studentId)
            ) {
                // In parent mode, only count this parent's meetings
                if (this.state.mode !== "teacher" && !entry.meeting.is_parent_meeting) continue;
                return true;
            }
        }
        return false;
    }

    /**
     * Return CSS classes for a student toggle-wrap element.
     * Computed once per student/teacher column (not per slot).
     *
     * Classes:
     *   is-selected-student        — teacher checkbox is ticked for this student
     *   has-booking-elsewhere      — student/teacher pair has a booking on any slot
     */
    getToggleWrapClasses(studentId, teacherId) {
        const parts = [];
        if ((this.state.selectedTeachers[studentId] || []).includes(teacherId)) {
            parts.push("is-selected-student");
        }
        if (this.isStudentTeacherBooked(studentId, teacherId)) {
            parts.push("has-booking-elsewhere");
        }
        return parts.join(" ");
    }

    /**
     * Students whose teacher selector is ticked for a particular column teacher.
     */
    getStudentsForTeacher(teacherId) {
        const students = [];
        const allStudents = this.getEffectiveStudents();
        for (const student of allStudents) {
            if ((this.state.selectedTeachers[student.id] || []).includes(teacherId)) {
                students.push(student);
            }
        }
        return students;
    }

    getInitials(name) {
        return getInitials(name);
    }

    getStudentOptionLabel(student) {
        const codes = student.classes.map((c) => c.class_code).join(", ");
        return codes ? student.name + " (" + codes + ")" : student.name;
    }

    onMainDropdownReady(api) {
        this._mainDropdownApi = api;
    }

    onStudentDropdownReady(api) {
        this._studentDropdownApi = api;
    }

    _setMainDropdownText(text) {
        if (this._mainDropdownApi) this._mainDropdownApi.setValue(text);
    }

    _setStudentDropdownText(text) {
        if (this._studentDropdownApi) this._studentDropdownApi.setValue(text);
    }

    _notify(msg, type) {
        this.notification.add(msg, { type });
    }
}

registry.category("actions").add("pti_ar.schedule_meetings", ScheduleMeetings);
