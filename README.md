# Kamin – Cinematic Produktspot (9:16, 15 s)

Aus einem einzigen Produktfoto (`assets/kamin_original.jpg`) gerechneter Werbespot.
Das Produkt wird nicht neu gemalt, sondern nur neu ausgeleuchtet und mit einer
virtuellen Kamera inszeniert – Design, Farben, Proportionen und Branding bleiben
wie fotografiert.

## Lieferung (`out/`)

| Datei | Inhalt |
|---|---|
| `kamin_basis_9x16.mp4` | Basisvideo 1080×1920, 30 fps, mit Ton, **ohne Text** – für CapCut |
| `kamin_vorschau_9x16.mp4` | Fertige Vorschau mit allen Texten und Logo-Platzhalter |
| `logo_platzhalter_1080x1920.png` | Logo-Platzhalter als transparente Ebene (deckungsgleich, ab 12,9 s) |
| `ton.wav` | Tonspur einzeln (synthetisch: Feuerknistern, Pad, Whooshes) |

## Ablauf

| Zeit | Einstellung | Bewegung / Effekt |
|---|---|---|
| 0,0–3,9 s | Hero, ganzer Kamin auf dunklem Grund | Aufblende aus dem Schwarz, langsamer Push-in, Lichtkante über das Glas |
| 3,1–7,1 s | Close-up Flammen | Drift nach links, Flackern, Hitzeflimmern, Glow |
| 6,3–10,1 s | Detail Glaskante oben rechts | Langsamer Push-in, Lichtreflex wandert übers Glas |
| 9,3–12,7 s | Detail Sockel mit Herstellerprägung | Pull-back, Streiflicht über den Stahl |
| 11,9–15,0 s | Finale Hero | Rückfahrt in die Totale, Endcard, Abblende |

Übergänge: 0,8 s Überblendung. Durchgehend leichtes Schweben (Drift + ±0,35° Rotation),
wanderndes warmes Führungslicht, Vignette, Filmkorn.

## Texte für CapCut (Spickzettel)

Farbe überall **#F3E6D3** (Creme), zentriert, weicher schwarzer Schatten (~55 %, Unschärfe 10).
Einblenden: 0,7 s Fade + 18 px von unten, Laufweite zieht sich leicht zusammen. Ausblenden: 0,6 s Fade.
Position = Oberkante des Texts in % der Bildhöhe (1920 px).

| Ein–Aus | Text | Schrift | Größe | Laufweite | Position |
|---|---|---|---|---|---|
| 0,9–3,4 s | FEUER. NEU GEDACHT. | Inter ExtraLight | 64 px | 14 px | 80 % |
| 3,9–6,6 s | Flammen, die den Raum verwandeln | Inter Light | 46 px | 2 px | 84 % |
| 7,1–9,6 s | Rundum-Blick aufs Feuer | Inter Light | 50 px | 3 px | 16 % |
| 10,0–12,2 s | MATT. SCHWARZ. ZEITLOS. | Inter ExtraLight | 54 px | 12 px | 84 % |
| 12,9–15,0 s | Wärme mit Stil. | Inter Display Light | 78 px | 3 px | 80 % |
| 13,4–15,0 s | JETZT IM FACHHANDEL ENTDECKEN | Inter Regular | 30 px | 8 px | 86,5 % |

Logo-Platzhalter: 12,9–15,0 s, oben mittig (9 % Höhe), durch das echte Kundenlogo ersetzen.

## Neu rendern

```bash
pip install --break-system-packages opencv-python-headless numpy pillow
python3 src/render.py base      # Video ohne Text (stumm)
python3 src/render.py preview   # Video mit Text (stumm)
python3 src/audio.py            # Tonspur
python3 src/render.py still 5   # Einzelbild zur Kontrolle -> out/still_05.00.jpg
```

Danach Ton auf -14 LUFS normalisieren und anlegen:
`ffmpeg -i out/ton.wav -af loudnorm=I=-14:TP=-1.5 -ar 48000 out/ton_n.wav`

`ffmpeg -i out/kamin_basis_9x16_stumm.mp4 -i out/ton.wav -c:v copy -c:a aac -b:a 192k -shortest out/kamin_basis_9x16.mp4`
