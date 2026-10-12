# API smoke tests

With the Flask server running at `http://127.0.0.1:5000`:

- `GET /health`
- `GET /api/dashboard`
- `GET /api/stations`
- `GET /api/vehicles`
- `GET /api/bookings`
- `GET /api/analytics`
- `GET /api/forecast`

Example vehicle registration in PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/vehicles -ContentType "application/json" -Body '{"owner":"Demo User","model":"Test EV","connector":"CCS2","battery_kwh":45,"soc":25}'
```

Example recommendation (replace vehicle_id with an ID from `/api/vehicles`):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/recommend -ContentType "application/json" -Body '{"vehicle_id":1,"target_soc":80,"priority":"normal","method":"smart"}'
```
