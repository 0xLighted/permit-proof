"""Demo-only automatic decisions. NFC is identification, not authentication."""
from uuid import uuid4
from contracts.schemas import DesiredState, Event, Person


def pages(person: Person, status: str) -> list[list[str]]:
    return [[person.name[:16], f"{person.role[:10]} {person.id}"[:16]], ["MOCK WORKFLOW", status[:16]]]


def transition(current: DesiredState, event: Event, people: dict) -> tuple[DesiredState, str]:
    state = current.model_copy(deep=True)
    state.revision += 1
    if event.kind == "session_reset":
        if state.phase == "active":
            return state, "Finish the active inspection before reset"
        return DesiredState(device_id=state.device_id, revision=state.revision), "Demo reset"
    if event.kind == "nfc_tapped":
        if state.phase == "active":
            return state, "Card ignored: finish the current inspection first"
        person = Person.model_validate(people[event.uid]) if event.uid in people else None
        state.person = person
        state.session_id = None
        if person is None:
            state.phase, state.led = "denied", "red"
            state.lcd_pages = [["Unknown card", "MOCK: denied"]]
            return state, "Unknown card"
        if not person.can_inspect:
            state.phase, state.led = "denied", "red"
            state.lcd_pages = pages(person, "Role not allowed")
            return state, "Demo role cannot start an inspection"
        state.phase, state.led = "ready", "green"
        state.lcd_pages = pages(person, "Press to start")
        return state, "Mock person recognised; not authenticated"
    if state.phase == "ready" and state.person:
        state.phase, state.led = "active", "green"
        state.session_id = str(uuid4())
        state.lcd_pages = pages(state.person, "Inspecting...")
        return state, "start_requested: accepted by MOCK policy"
    if state.phase == "active" and state.person:
        state.phase, state.led = "complete", "green"
        state.lcd_pages = pages(state.person, "Job complete")
        return state, "completion_requested: accepted by MOCK policy"
    state.led = "yellow"
    state.lcd_pages = [["Scan card first", "MOCK WORKFLOW"]]
    return state, "inspection_requested: scan an allowed card first"
