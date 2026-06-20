# Project Conventions

## API Compatibility Testing

When modifying backend API endpoints or frontend API calls, ALWAYS verify compatibility:

1. **Backend changes**: After modifying routes, request/response schemas, or adding new endpoints:
   - Test the endpoint with curl to verify it works
   - Check that request/response JSON matches what frontend expects
   - Verify error handling returns appropriate status codes

2. **Frontend changes**: After modifying API client functions or adding new calls:
   - Verify the frontend types match the backend response shape
   - Test that the frontend can successfully call the endpoint
   - Check error handling for failed requests

3. **Integration testing**: When both frontend and backend change:
   - Start both servers (backend on :8000, frontend on :3000)
   - Test the full flow from UI action → API call → database → UI update
   - Verify data flows correctly in both directions

4. **Type safety**: Ensure TypeScript types in `frontend/lib/types.ts` and `frontend/lib/api.ts` match the actual backend response structure.

## Testing Commands

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload

# Frontend  
cd frontend && npm run dev

# Test endpoint
curl -s http://localhost:8000/runs/apps | jq .

# Build check
cd frontend && npm run build
```

## Database

- Supabase project: `ffedvcwvvkdstzlvxxhr`
- Use `supabase_execute_sql` for queries
- Use `supabase_apply_migration` for schema changes
- Always verify migrations success before proceeding

## Code Style

- Follow existing patterns in the codebase
- Use existing utilities and libraries (don't add new dependencies unless necessary)
- Keep changes minimal and focused
- Test before committing
