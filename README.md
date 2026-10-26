# Rețele Electrice - Întreruperi (Home Assistant)

Integrare custom care citește din contul de pe `contulmeu.reteleelectrice.ro`
dacă există o întrerupere de curent pentru un POD.

## Entități
- `sensor` **Întreruperi curent**: „Fără întreruperi" / „Întrerupere activă" (atribute: `pod`, `mesaj`, `checkInterruzione`)
- `binary_sensor` **Întrerupere activă** (clasa `problem`)

## Instalare (HACS)
1. HACS → ⋮ → **Custom repositories** → adaugă URL-ul acestui repo, categoria **Integration**.
2. Instalează „Rețele Electrice - Întreruperi" și repornește Home Assistant.
3. Setări → Dispozitive și Servicii → Adaugă integrare → email, parolă, POD.

Intervalul de actualizare implicit e 1 oră (minim 15 minute), configurabil din Configurare.

## Depanare
```yaml
logger:
  logs:
    custom_components.re_intreruperi: debug
```

## Notă
Folosește portalul web al Rețele Electrice (nu un API oficial); se poate strica dacă portalul se schimbă.
Datele de autentificare rămân doar în Home Assistant.
