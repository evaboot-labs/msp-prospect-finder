# The companies your MSP looks for

Status: EXAMPLE

The agent reads this file before every search. Replace the example with your own territory and verticals, then set `Status: yours`.

The example is a managed service provider in Dallas-Fort Worth that sells to law firms, CPA firms and medical practices.

## Account search (Sales Navigator filters)

- Headquarters location: Dallas-Fort Worth Metroplex
- Industry: Law Practice; Accounting; Medical Practices
- Company headcount: 11-50; 51-200
- Department headcount: Information Technology, 0 to 2
- Company headcount growth: more than 10% in one year

## Scoring (read by msp.py)

- territory: Dallas; Fort Worth; Plano; Irving; Frisco; Richardson; Addison; Arlington; McKinney; Allen; Carrollton; Grapevine; Southlake; Denton; Lewisville
- it_staff_max: 2
- seats_min: 20
- seats_max: 150
- growth_min: 10
- growth_high: 25
- keep_score: 5
- office_words: offices in; locations in; new office; second office; clinics in

Points: no IT person on LinkedIn +3, one +2, two or more up to `it_staff_max` +1 (more: dropped). Headcount between `seats_min` and `seats_max` +1. One-year headcount growth at or above `growth_min` +2 (at or above `growth_high` +3). Description with an `office_words` phrase (several sites to connect) +1. A company whose headquarters address has no `territory` city among its parts is dropped: an MSP sells where it can send a technician. A company is kept at `keep_score` or more.

## Who to reach at each company

- lead_area: Texas; Dallas-Fort Worth
- titles: Owner; Managing Partner; COO; Chief Operating Officer; Firm Administrator; Practice Administrator; Practice Manager; Office Manager; Operations Manager; Director of Operations; IT Manager; Systems Administrator

`lead_area` drops the people based elsewhere (a partner who runs another office). In a firm with no IT team, IT is bought by the owner, the operations lead or the office manager. The IT titles find the first IT hire, who wants help, not a replacement.
