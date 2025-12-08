# Crowdfunding Back End

### Becky Cole

## Planning:

### Concept/Name - Backyard Festival – Crowdfunding Platform for Events on a Shoestring!

Backyard Festival is a full-stack crowdfunding platform designed to help event organisers run grassroots/small-to-medium community events such as local music concerts, bachelorette parties, Church functions, school fundraisers, street marches, charity bike rides etc.

Unlike traditional crowdfunding sites which only support money, Backyard Festival allows supporters to contribute money, items, or time, and lets event hosts assign reward tiers for all three contribution types.

This is to model how micro events work in reality (especially in the not for profit sector), where you need money (eg venue hire), time (volunteers to run the event) and items (e.g. microphones, PA system) to get local events up and running.

Organisers create a fundraiser, define their needs (money, item, or volunteer time), set optional rewards, and supporters can pledge directly against those needs.

It is envisaged that the platform would eventually be a community platform where people can support each other projects, volunteer for various projects, earn rewards and recommendations from event organisers.

This would long term be invaluable for students wanting to break into events/music who need experience to put on their resume. It also acknowledges that micro-events can often be pulled together through sharing equipment and resources, ultimately with the aim of providing more opportunities for people to create and host more events in the community.

### Intended Audience/User Stories

#### Intended Audience

Community organisers running events (festivals, concerts, school events, charity nights)

- Volunteers wanting to offer skills or time

- Supporters wanting to donate money or items

- Small groups needing a centralised place to coordinate resources

### Key User Stories

As an organiser:

- I want to create a fundraiser and list all the needs required for my event.

- I want to specify whether a need requires money, time, or items.

- I want to attach reward tiers to encourage certain contributions.

- I want to track all pledges and see which needs are filled or still open.

As a supporter:

- I want to browse events and see what they need.

- I want to pledge money, volunteer my time, or loan/donate items.

- I want to see what reward I’ll get for my contribution.

- I want to edit my pledge if my plans or availability change.

### Front End Pages/Functionality

- {{ A page on the front end }}
  - {{ A list of dot-points showing functionality is available on this page }}
  - {{ etc }}
  - {{ etc }}
- {{ A second page available on the front end }}
  - {{ Another list of dot-points showing functionality }}
  - {{ etc }}

### API Spec

# API Specification

All endpoints return and accept JSON.  
Authentication is via **Token Auth** using:

- `POST /api-token-auth/` with `username` and `password`
- Then send `Authorization: Token <your-token>` in headers for authenticated actions.

---

## Fundraisers

### Endpoints

| URL                  | Method | Purpose                                | Request Body                                                                                                                | Success | Auth       |
| -------------------- | ------ | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------- | ---------- |
| `/fundraisers/`      | GET    | List all fundraisers                   | –                                                                                                                           | 200     | None       |
| `/fundraisers/`      | POST   | Create a fundraiser                    | `title`, `description`, `goal`, `image_url`, `location`, `start_date`, `end_date`, `status`, `enable_rewards`, `sort_order` | 201     | Logged-in  |
| `/fundraisers/<id>/` | GET    | Retrieve a single fundraiser           | –                                                                                                                           | 200     | None       |
| `/fundraisers/<id>/` | PUT    | Update fundraiser                      | Same fields as POST (partial updates allowed)                                                                               | 200     | Owner only |
| `/fundraisers/<id>/` | DELETE | Delete fundraiser (only if no pledges) | –                                                                                                                           | 204     | Owner only |

### Example: Create Fundraiser (POST `/fundraisers/`)

```json
{
  "title": "Backyard Festival 2025",
  "description": "A mini community festival with music, food and games.",
  "goal": "5000.00",
  "image_url": "https://example.com/festival.jpg",
  "location": "Brisbane backyard, West End",
  "start_date": "2025-12-05",
  "end_date": "2025-12-05",
  "status": "active",
  "enable_rewards": true,
  "sort_order": 1
}
```

## Needs (Base Need)

| URL            | Method | Purpose                          | Request Body                                                                          | Success | Auth             |
| -------------- | ------ | -------------------------------- | ------------------------------------------------------------------------------------- | ------- | ---------------- |
| `/needs/`      | GET    | List all needs                   | –                                                                                     | 200     | None             |
| `/needs/`      | POST   | Create a base need               | `fundraiser`, `need_type`, `title`, `description`, `status`, `priority`, `sort_order` | 201     | Fundraiser owner |
| `/needs/<id>/` | GET    | Retrieve a single need           | –                                                                                     | 200     | None             |
| `/needs/<id>/` | PUT    | Update need                      | Same fields as POST (partial updates allowed)                                         | 200     | Fundraiser owner |
| `/needs/<id>/` | DELETE | Delete need (only if no pledges) | –                                                                                     | 204     | Fundraiser owner |

Example: Create Need (POST/Needs)

```json
{
  "fundraiser": 8,
  "need_type": "money",
  "title": "Money for pizza and beer for the crew",
  "description": "Pepperoni and pineapple all round!",
  "status": "open",
  "priority": "high",
  "sort_order": 1
}
```

## Need Detail Models

These add extra fields for each type of need.
Each is linked by a OneToOne relationship to a base Need.

### Money Need

| URL                  | Method | Purpose              | Request Body                       | Success | Auth             |
| -------------------- | ------ | -------------------- | ---------------------------------- | ------- | ---------------- |
| `/money-needs/`      | GET    | List all money needs | –                                  | 200     | None             |
| `/money-needs/`      | POST   | Create MoneyNeed     | `need`, `target_amount`, `comment` | 201     | Fundraiser owner |
| `/money-needs/<id>/` | GET    | Retrieve MoneyNeed   | –                                  | 200     | None             |
| `/money-needs/<id>/` | PUT    | Update MoneyNeed     | `target_amount`, `comment`         | 200     | Fundraiser owner |
| `/money-needs/<id>/` | DELETE | Delete MoneyNeed     | –                                  | 204     | Fundraiser owner |

### Example Create Money Need (POST/money-needs)

```json
{
  "need": 8,
  "target_amount": "600.00",
  "comment": "Total amount for pizza for the crew."
}
```

### DB Schema

![]( {{ ./relative/path/to/your/schema/image.png }} )

```

```
