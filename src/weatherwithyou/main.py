from fastapi import FastAPI

from weatherwithyou.api.routes.weather_routes import router as weather_router


app = FastAPI(
    title="Weather With You API",
    version="0.1.0",
)

app.include_router(weather_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
