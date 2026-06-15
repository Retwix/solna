# Solna

**Solna** is a SaaS that helps photographers and event creators deliver photos to their guests as fast as possible — automatically, using facial recognition.

A photographer shoots an event. Each photo is uploaded the moment it's taken, processed and sorted on the server, and made instantly findable. A guest scans a QR code, takes a selfie, and sees every photo they appear in. No manual sorting, no waiting days for a gallery.

---

## The problem

At events — weddings, conferences, festivals, sports — photographers shoot hundreds or thousands of photos. Guests then wait days or weeks for an edited gallery, and even then have to scroll through everything to find shots of themselves. Solna closes that gap to near real-time.

## How it works

Solna connects three pieces: the **photographer's camera**, the **Solna server**, and the **end user's phone**.

### 1. Photographer → Server (capture & upload)

Most professional cameras can push images over **FTP** the instant they're shot (or via a tethered/Wi-Fi setup). The photographer points this FTP feed at a dedicated repository on the Solna server. As they shoot, photos flow in automatically — no card swapping, no manual upload.

### 2. Server (automatic processing)

When the server receives a new image, it runs an automated pipeline:

- **Facial analysis** — detects and encodes the faces present in each photo so they can later be matched against guests.
- **Pre-sorting** — groups and tags photos automatically (e.g. by the people detected), so the gallery is organized without manual effort.
- **Filtering / styling** — applies a custom look to each photo, similar to a Lightroom preset, so delivered images are already polished.

### 3. End user → Gallery (find & receive)

The guest experience is built around a QR code displayed at the event:

1. The guest **scans the QR code** and lands on the Solna landing page.
2. They **take a selfie** and enter their **email address**.
3. Solna matches their face against every processed photo and shows an **index of all pictures they appear in**.

The result: each guest gets a personal gallery of just the photos featuring them, available almost as fast as the photographer can shoot.

## Core flow at a glance

```
Photographer's camera
        │  (FTP, auto-upload on capture)
        ▼
   Solna server  ──►  Facial analysis  ──►  Pre-sort  ──►  Custom filter/preset
        │
        ▼
   Indexed, styled photos
        │
        ▼
End user scans QR  ──►  Selfie + email  ──►  Personal gallery (all photos they're in)
```

## Key concepts

| Term | Meaning |
|------|---------|
| **Photographer feed** | The FTP connection from a camera to a dedicated repo on the server. |
| **Repository** | Per-event storage on the server where incoming photos land. |
| **Facial analysis** | Detecting and encoding faces in each photo for later matching. |
| **Pre-sorting** | Automatic grouping/tagging of photos as they arrive. |
| **Custom filter** | A preset-style look applied automatically to delivered photos. |
| **Selfie match** | Matching a guest's selfie against processed photos to build their gallery. |
| **QR onboarding** | The scan → selfie → email entry point for end users. |

## Who it's for

- **Photographers** who want to deliver fast and cut hours of culling and sorting.
- **Event creators / organizers** who want guests to leave with their photos already in hand.
- **Guests** who want their pictures without scrolling through an entire event's gallery.

---

*This is an early project overview. Setup instructions, tech stack, and repo structure will be added as the project takes shape.*
