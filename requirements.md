# Pen Relay - Performance, Bugfix & Responsiveness Improvements

## Performance Issues

### P1: Canvas redraws and settings saves on every drag event
**Problem:** MapEditor triggers full canvas redraw + disk write on every single mouse movement
**Solution:** Debounce settings updates to 500ms, only redraw canvas when values actually change significantly
**Impact:** Reduces I/O and rendering by 90%+

### P2: WebSocket sends all pointer events without throttling
**Problem:** Rapid pointer moves (60+ events/sec) all sent individually, causing network overhead
**Solution:** Implement client-side throttling (send max 60 events/sec, coalesce moves)
**Impact:** Reduces bandwidth usage by 30-50%

### P3: QR code regenerated during runtime
**Problem:** QR code generated and converted to PhotoImage on every server start
**Solution:** Generate QR once, cache the PhotoImage
**Impact:** Eliminates unnecessary image processing

### P4: Settings written to disk on every drag
**Problem:** Calls to `settings.update()` write JSON file immediately
**Solution:** Use debouncing decorator for file writes (batch changes)
**Impact:** Reduces disk I/O by 95%

## Bugfixes

### B1: MapEditor refresh loop always active
**Problem:** `refresh()` redraws canvas every 400ms even when nothing changed
**Solution:** Make refresh only update when aspect ratio changes, not continuous
**Impact:** Reduces CPU usage

### B2: Pressure not passed to UP events
**Problem:** `pen.inject(pen.INRANGE|pen.UP,x,y)` called without pressure parameter
**Solution:** Pass pressure parameter to all inject calls for consistency
**Impact:** Ensures smooth pointer state transitions

### B3: No pressure validation
**Problem:** Pressure values from client not validated before use
**Solution:** Clamp pressure to [0, 1] range with validation
**Impact:** Prevents invalid state and Windows API issues

### B4: Missing error handling for bad pointer data
**Problem:** Malformed messages silently skipped with bare `continue`
**Solution:** Add logging or graceful degradation for invalid data
**Impact:** Better debugging and robustness

### B5: No connection status feedback to mobile client
**Problem:** Mobile app doesn't know if server received data or lost connection
**Solution:** Send periodic ping/status messages from server to client
**Impact:** Better UX for mobile user

## Smoothness & Responsiveness

### R1: No client-side connection feedback
**Problem:** User doesn't know if connection is active, latency, or data flowing
**Solution:** Add connection status UI on mobile (connected/disconnected indicator)
**Impact:** Better user awareness

### R2: Event drain loop too slow
**Problem:** 100ms drain loop may batch events too much
**Solution:** Increase drain frequency to 16ms (60 FPS) for snappier UI updates
**Impact:** More responsive UI feedback

### R3: Pointer throttling missing
**Problem:** No rate limiting on client pointer events
**Solution:** Throttle pointer moves to 60 Hz on client
**Impact:** Smoother network utilization and less lag

## Requirements

### Must Have (MVP)
- Debounce canvas redraws in MapEditor
- Debounce settings file writes
- Fix pressure parameter on UP events
- Add pressure validation [0, 1]
- Increase drain loop frequency to 16ms
- QR cache optimization

### Should Have (High Priority)
- Client-side pointer throttling
- Connection status indicator on mobile
- Error handling for malformed data
- Smart refresh in MapEditor (only when needed)

### Nice to Have (Lower Priority)
- Server-side event batching
- Latency metrics display
