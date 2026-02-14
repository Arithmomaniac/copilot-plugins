# Spec: {{CAPABILITY_NAME}}

<!-- One spec file per capability listed in the proposal's Capabilities section.
     - New capabilities: use the exact kebab-case name from the proposal.
     - Modified capabilities: use the existing spec folder name.
     
     Use SHALL/MUST for normative requirements (avoid should/may).
     Every requirement MUST have at least one scenario.
     Scenarios MUST use exactly 4 hashtags (####). -->

## Purpose

<!-- High-level description of this spec's domain -->

## ADDED Requirements

### Requirement: <!-- requirement name -->
<!-- The system SHALL/MUST ... (describe the required behavior) -->

#### Scenario: <!-- scenario name (happy path) -->
- **GIVEN** <!-- precondition / initial state -->
- **WHEN** <!-- action or event -->
- **THEN** <!-- expected outcome -->
- **AND** <!-- additional outcome (optional) -->

#### Scenario: <!-- scenario name (edge case / error) -->
- **GIVEN** <!-- precondition / initial state -->
- **WHEN** <!-- action or event -->
- **THEN** <!-- expected outcome -->

## MODIFIED Requirements

<!-- Changed behavior — MUST include full updated requirement content.
     Copy the ENTIRE existing requirement block, paste here, then edit.
     Header text must match the original exactly (whitespace-insensitive). -->

### Requirement: <!-- existing requirement name -->
<!-- Full updated requirement text -->

#### Scenario: <!-- updated scenario -->
- **GIVEN** <!-- precondition -->
- **WHEN** <!-- action -->
- **THEN** <!-- new expected outcome -->

## REMOVED Requirements

<!-- Deprecated features — MUST include Reason and Migration. -->

### Requirement: <!-- requirement being removed -->
**Reason:** <!-- why this is being removed -->
**Migration:** <!-- how users should adapt -->
