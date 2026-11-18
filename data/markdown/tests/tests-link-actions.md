# Link actions {#top}

Every kind of click md2ui reports. A click never changes this document; the agent answers by sending it again.

## Ask the user {#ask}

Want me to generate the quarterly report?

[Yes](agent:generate-report?format=pdf&year=2026) *[No](agent:cancel)*

## An answered question {#answered}

Want me to email it to the team?

[Yes](agent:email-report) ~~*[No](agent:cancel)*~~

## Pick a plan {#plans}

[
### Starter
$9 a month

For one person.

[Choose](agent:choose-plan?plan=starter)
](agent:choose-plan?plan=starter)

[
### Team
$29 a month

For up to ten people.

[Choose](agent:choose-plan?plan=team)
](agent:choose-plan?plan=team)

## Go somewhere {#links}

[Documentation](https://example.com/docs) **[Contact us](mailto:team@example.com)** *[Settings](/settings)*

[`Back to top`](#top) [`Plans`](#plans)

## Tasks {#tasks}

- [x] Draft the report
- [ ] Review the numbers
- [[ ]](agent:toggle-task?id=3) Send it to finance

## In a sentence {#prose}

Read the [pricing notes](#plans) before you choose, or ask to [talk to sales](agent:contact-sales).
