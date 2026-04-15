import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudSnow,
  Compass,
  Download,
  LoaderCircle,
  MapPin,
  Search,
  Sun,
  Wind,
} from "lucide-react";

const WEATHER_ROUTE = "/weather";
const EXPORT_ROUTE = "/weather/export";

const INITIAL_LOCATION = "London, Ontario, Canada";

function decodeHtmlEntities(value) {
  if (typeof window === "undefined") {
    return value;
  }

  const parser = new DOMParser();
  const documentFragment = parser.parseFromString(value, "text/html");
  return documentFragment.documentElement.textContent || value;
}

function weatherCodeMeta(code) {
  if (code === 0) {
    return { label: "Clear", icon: Sun };
  }

  if ([1, 2, 3].includes(code)) {
    return { label: "Cloudy", icon: Cloud };
  }

  if ([45, 48].includes(code)) {
    return { label: "Fog", icon: CloudFog };
  }

  if ([51, 53, 55, 56, 57].includes(code)) {
    return { label: "Drizzle", icon: CloudDrizzle };
  }

  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) {
    return { label: "Rain", icon: CloudRain };
  }

  if ([71, 73, 75, 77, 85, 86].includes(code)) {
    return { label: "Snow", icon: CloudSnow };
  }

  if ([95, 96, 99].includes(code)) {
    return { label: "Storm", icon: CloudLightning };
  }

  return { label: "Weather", icon: Cloud };
}

function aggregateFiveDayForecast(forecastPayload) {
  const hourly = forecastPayload?.hourly;
  if (!hourly?.time?.length) {
    return [];
  }

  const groupedByDay = new Map();

  // The backend returns an hourly forecast window. We collapse that into
  // day-level cards here so the frontend can show a clear five-day forecast.
  hourly.time.forEach((timestamp, index) => {
    const dayKey = timestamp.slice(0, 10);

    if (!groupedByDay.has(dayKey)) {
      groupedByDay.set(dayKey, {
        dayKey,
        temperatures: [],
        windSpeeds: [],
        weatherCodes: [],
        precipitation: [],
      });
    }

    const day = groupedByDay.get(dayKey);
    day.temperatures.push(hourly.temperature_2m?.[index] ?? null);
    day.windSpeeds.push(hourly.wind_speed_10m?.[index] ?? null);
    day.weatherCodes.push(hourly.weather_code?.[index] ?? null);
    day.precipitation.push(hourly.precipitation?.[index] ?? null);
  });

  return Array.from(groupedByDay.values())
    .slice(0, 5)
    .map((day) => {
      const temperatures = day.temperatures.filter((value) => value !== null);
      const windSpeeds = day.windSpeeds.filter((value) => value !== null);
      const precipitation = day.precipitation.filter((value) => value !== null);
      const weatherCodes = day.weatherCodes.filter((value) => value !== null);

      const high = temperatures.length ? Math.max(...temperatures) : null;
      const low = temperatures.length ? Math.min(...temperatures) : null;
      const peakWind = windSpeeds.length ? Math.max(...windSpeeds) : null;
      const totalPrecipitation = precipitation.length
        ? precipitation.reduce((sum, value) => sum + value, 0)
        : null;
      const representativeCode = weatherCodes[Math.floor(weatherCodes.length / 2)] ?? null;

      return {
        date: day.dayKey,
        high,
        low,
        peakWind,
        totalPrecipitation,
        weatherCode: representativeCode,
      };
    });
}

async function requestWeather({ locationInput, mode, startDateTime, endDateTime, include = [] }) {
  const payload = {
    locationInput,
    mode,
    units: "metric",
    include,
  };

  if (startDateTime) {
    payload.startDateTime = startDateTime;
  }

  if (endDateTime) {
    payload.endDateTime = endDateTime;
  }

  const response = await fetch(WEATHER_ROUTE, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok) {
    const message =
      data?.detail?.error?.message || data?.error?.message || "Unable to retrieve weather right now.";
    throw new Error(message);
  }

  return data;
}

function downloadExport(format) {
  window.open(`${EXPORT_ROUTE}?format=${format}`, "_blank", "noopener,noreferrer");
}

export default function App() {
  const [locationInput, setLocationInput] = useState(INITIAL_LOCATION);
  const [submittedLocation, setSubmittedLocation] = useState(INITIAL_LOCATION);
  const [currentWeather, setCurrentWeather] = useState(null);
  const [forecastWeather, setForecastWeather] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const forecastCards = useMemo(
    () => aggregateFiveDayForecast(forecastWeather?.weatherData?.payload),
    [forecastWeather],
  );

  async function loadWeather(nextLocation) {
    setIsLoading(true);
    setErrorMessage("");

    const now = new Date();
    const forecastStart = new Date(now);
    forecastStart.setUTCHours(0, 0, 0, 0);
    const forecastEnd = new Date(forecastStart);
    forecastEnd.setUTCDate(forecastEnd.getUTCDate() + 4);
    forecastEnd.setUTCHours(23, 0, 0, 0);

    try {
      const [currentResponse, forecastResponse] = await Promise.all([
        requestWeather({
          locationInput: nextLocation,
          mode: "current",
          include: ["map", "youtube", "pun"],
        }),
        requestWeather({
          locationInput: nextLocation,
          mode: "forecast",
          startDateTime: forecastStart.toISOString(),
          endDateTime: forecastEnd.toISOString(),
        }),
      ]);

      setCurrentWeather(currentResponse);
      setForecastWeather(forecastResponse);
      setSubmittedLocation(nextLocation);
    } catch (error) {
      setCurrentWeather(null);
      setForecastWeather(null);
      setErrorMessage(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    loadWeather(locationInput.trim());
  }

  function handleUseMyLocation() {
    if (!navigator.geolocation) {
      setErrorMessage("Your browser does not support geolocation.");
      return;
    }

    setIsLocating(true);
    setErrorMessage("");

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextLocation = `${position.coords.latitude}, ${position.coords.longitude}`;
        setLocationInput(nextLocation);
        setIsLocating(false);
        loadWeather(nextLocation);
      },
      () => {
        setIsLocating(false);
        setErrorMessage("We couldn't access your current location. Please enter one manually.");
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
      },
    );
  }

  useEffect(() => {
    loadWeather(INITIAL_LOCATION);
  }, []);

  const currentPayload = currentWeather?.weatherData?.payload?.current;
  const currentCodeMeta = weatherCodeMeta(currentPayload?.weather_code ?? null);
  const CurrentIcon = currentCodeMeta.icon;
  const enrichment = currentWeather?.enrichment;

  return (
    <div
      style={{
        minHeight: "100vh",
        padding: "32px 20px 48px",
      }}
    >
      <div
        style={{
          maxWidth: "1180px",
          margin: "0 auto",
          display: "grid",
          gap: "24px",
        }}
      >
        <header
          style={{
            display: "grid",
            gap: "10px",
          }}
        >
          <p
            style={{
              margin: 0,
              color: "#46617f",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              fontSize: "0.82rem",
              fontWeight: 700,
            }}
          >
            Weather With You
          </p>
          <h1
            style={{
              margin: 0,
              fontSize: "clamp(2rem, 4vw, 4rem)",
              lineHeight: 1,
            }}
          >
            Weather App by Isaac Hua
          </h1>
          <p
            style={{
              margin: 0,
              maxWidth: "72ch",
              color: "#46617f",
            }}
          >
            Search by town, city, landmark, postal code, or coordinates. 
            
            You can also use your current location, pull live enrichment, and export saved weather data straight from the
            database.


            Done as part of PM Accelerator, this is their associated overview:
            ""
          </p>
        </header>

        <section
          style={{
            background: "rgba(255, 255, 255, 0.72)",
            border: "1px solid rgba(18, 32, 51, 0.08)",
            backdropFilter: "blur(14px)",
            borderRadius: "28px",
            padding: "24px",
            boxShadow: "0 24px 60px rgba(27, 53, 87, 0.08)",
          }}
        >
          <form
            onSubmit={handleSubmit}
            style={{
              display: "grid",
              gap: "16px",
            }}
          >
            <label
              htmlFor="location-input"
              style={{
                display: "grid",
                gap: "8px",
                fontWeight: 600,
              }}
            >
              Location
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto auto",
                  gap: "12px",
                }}
              >
                <input
                  id="location-input"
                  value={locationInput}
                  onChange={(event) => setLocationInput(event.target.value)}
                  placeholder="Try London, Ontario, Canada or 42.9837, -81.2496"
                  style={{
                    width: "100%",
                    padding: "16px 18px",
                    borderRadius: "16px",
                    border: "1px solid rgba(18, 32, 51, 0.14)",
                    background: "white",
                  }}
                />
                <button
                  type="submit"
                  disabled={isLoading || !locationInput.trim()}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    border: 0,
                    borderRadius: "16px",
                    padding: "0 18px",
                    background: "#14263f",
                    color: "white",
                    cursor: "pointer",
                    minHeight: "54px",
                  }}
                >
                  {isLoading ? <LoaderCircle size={18} /> : <Search size={18} />}
                  Search
                </button>
                <button
                  type="button"
                  onClick={handleUseMyLocation}
                  disabled={isLocating || isLoading}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    border: "1px solid rgba(18, 32, 51, 0.14)",
                    borderRadius: "16px",
                    padding: "0 18px",
                    background: "rgba(255,255,255,0.82)",
                    color: "#14263f",
                    cursor: "pointer",
                    minHeight: "54px",
                  }}
                >
                  {isLocating ? <LoaderCircle size={18} /> : <Compass size={18} />}
                  Use my location
                </button>
              </div>
            </label>

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <button
                type="button"
                onClick={() => downloadExport("json")}
                style={exportButtonStyle}
              >
                <Download size={16} />
                Export JSON
              </button>
              <button
                type="button"
                onClick={() => downloadExport("csv")}
                style={exportButtonStyle}
              >
                <Download size={16} />
                Export CSV
              </button>
            </div>

            {errorMessage ? (
              <div style={errorBannerStyle}>
                <AlertTriangle size={18} />
                <span>{errorMessage}</span>
              </div>
            ) : null}
          </form>
        </section>

        <section
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 2fr) minmax(300px, 1fr)",
            gap: "24px",
          }}
        >
          <article style={panelStyle}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: "20px",
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "grid", gap: "10px" }}>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    color: "#46617f",
                    fontWeight: 600,
                  }}
                >
                  <MapPin size={16} />
                  {currentWeather?.normalizedLocation || submittedLocation}
                </div>
                <h2
                  style={{
                    margin: 0,
                    fontSize: "1.1rem",
                    color: "#46617f",
                  }}
                >
                  Current weather
                </h2>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "16px",
                  }}
                >
                  <CurrentIcon size={56} />
                  <div>
                    <div style={{ fontSize: "clamp(2.6rem, 8vw, 5rem)", fontWeight: 700 }}>
                      {currentPayload?.temperature_2m ?? "--"}°
                    </div>
                    <div style={{ color: "#46617f", fontWeight: 600 }}>{currentCodeMeta.label}</div>
                  </div>
                </div>
              </div>

              {enrichment?.pun ? (
                <aside
                  style={{
                    maxWidth: "320px",
                    padding: "18px",
                    borderRadius: "20px",
                    background: "linear-gradient(135deg, #14263f, #274b78)",
                    color: "white",
                  }}
                >
                  <p
                    style={{
                      margin: "0 0 8px",
                      fontSize: "0.78rem",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      opacity: 0.76,
                    }}
                  >
                    Live pun
                  </p>
                  <p style={{ margin: 0, fontSize: "1.02rem", lineHeight: 1.5 }}>
                    {enrichment.pun.text}
                  </p>
                </aside>
              ) : null}
            </div>

            <div
              style={{
                marginTop: "22px",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: "12px",
              }}
            >
              <MetricCard
                icon={<Sun size={18} />}
                label="Feels like"
                value={currentPayload?.apparent_temperature != null ? `${currentPayload.apparent_temperature}°` : "--"}
              />
              <MetricCard
                icon={<Wind size={18} />}
                label="Wind"
                value={currentPayload?.wind_speed_10m != null ? `${currentPayload.wind_speed_10m} km/h` : "--"}
              />
              <MetricCard
                icon={<CloudRain size={18} />}
                label="Precipitation"
                value={currentPayload?.precipitation != null ? `${currentPayload.precipitation} mm` : "--"}
              />
              <MetricCard
                icon={<Cloud size={18} />}
                label="Cloud cover"
                value={currentPayload?.cloud_cover != null ? `${currentPayload.cloud_cover}%` : "--"}
              />
            </div>
          </article>

          <aside style={panelStyle}>
            <h2 style={{ marginTop: 0, marginBottom: "16px" }}>Live extras</h2>
            <div style={{ display: "grid", gap: "16px" }}>
              <div style={subtleBlockStyle}>
                <h3 style={subtleHeadingStyle}>Map</h3>
                {enrichment?.map ? (
                  <div style={{ display: "grid", gap: "10px" }}>
                    <div
                      style={{
                        overflow: "hidden",
                        borderRadius: "16px",
                        border: "1px solid rgba(18, 32, 51, 0.08)",
                        background: "#dfeafb",
                        minHeight: "220px",
                      }}
                    >
                      <iframe
                        title={`Map for ${enrichment.map.query}`}
                        src={enrichment.map.embedUrl}
                        style={{
                          width: "100%",
                          height: "220px",
                          border: 0,
                        }}
                        loading="lazy"
                        referrerPolicy="no-referrer-when-downgrade"
                      />
                    </div>
                    <a href={enrichment.map.embedUrl} target="_blank" rel="noreferrer" style={linkStyle}>
                      Open this map in a new tab
                    </a>
                  </div>
                ) : (
                  <p style={emptyTextStyle}>Map enrichment is unavailable right now.</p>
                )}
              </div>

              <div style={subtleBlockStyle}>
                <h3 style={subtleHeadingStyle}>Videos</h3>
                {enrichment?.youtubeVideos?.length ? (
                  <div style={{ display: "grid", gap: "10px" }}>
                    {enrichment.youtubeVideos.slice(0, 3).map((video) => (
                      <article
                        key={video.videoId}
                        style={videoLinkStyle}
                      >
                        <div
                          style={{
                            overflow: "hidden",
                            borderRadius: "14px",
                            background: "#09111d",
                            aspectRatio: "16 / 9",
                          }}
                        >
                          <iframe
                            title={decodeHtmlEntities(video.title)}
                            src={video.embedUrl}
                            style={{
                              width: "100%",
                              height: "100%",
                              border: 0,
                            }}
                            loading="lazy"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                            referrerPolicy="strict-origin-when-cross-origin"
                            allowFullScreen
                          />
                        </div>
                        <strong style={{ display: "block", marginBottom: "4px" }}>
                          {decodeHtmlEntities(video.title)}
                        </strong>
                        <span style={{ color: "#46617f", fontSize: "0.9rem" }}>
                          {decodeHtmlEntities(video.channelTitle)}
                        </span>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p style={emptyTextStyle}>No live YouTube suggestions are available right now.</p>
                )}
              </div>
            </div>
          </aside>
        </section>

        <section style={panelStyle}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >
            <h2 style={{ margin: 0 }}>Five-day forecast</h2>
            <span style={{ color: "#46617f" }}>
              Built from the backend&apos;s hourly forecast data.
            </span>
          </div>

          <div
            style={{
              marginTop: "18px",
              display: "grid",
              gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
              gap: "14px",
            }}
          >
            {forecastCards.map((day) => {
              const meta = weatherCodeMeta(day.weatherCode);
              const DayIcon = meta.icon;

              return (
                <div
                  key={day.date}
                  style={{
                    padding: "18px",
                    borderRadius: "22px",
                    background: "rgba(243, 247, 255, 0.92)",
                    border: "1px solid rgba(18, 32, 51, 0.08)",
                    display: "grid",
                    gap: "10px",
                  }}
                >
                  <div style={{ color: "#46617f", fontWeight: 700 }}>
                    {new Date(`${day.date}T12:00:00Z`).toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </div>
                  <DayIcon size={24} />
                  <div style={{ fontWeight: 700 }}>{meta.label}</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                    {day.high != null ? `${Math.round(day.high)}°` : "--"}
                    <span style={{ color: "#6c839d", fontSize: "0.95rem", marginLeft: "6px" }}>
                      {day.low != null ? `${Math.round(day.low)}°` : "--"}
                    </span>
                  </div>
                  <div style={{ color: "#46617f", fontSize: "0.92rem" }}>
                    Rain: {day.totalPrecipitation != null ? `${day.totalPrecipitation.toFixed(1)} mm` : "--"}
                  </div>
                  <div style={{ color: "#46617f", fontSize: "0.92rem" }}>
                    Wind: {day.peakWind != null ? `${Math.round(day.peakWind)} km/h` : "--"}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section style={panelStyle}>
          <div
            style={{
              display: "grid",
              gap: "12px",
            }}
          >
            <h2 style={{ margin: 0 }}>Description</h2>
            <div
              style={{
                minHeight: "180px",
                borderRadius: "22px",
                border: "1px dashed rgba(18, 32, 51, 0.18)",
                background: "rgba(243, 247, 255, 0.92)",
                padding: "20px",
                display: "grid",
                gap: "16px",
                alignContent: "start",
                color: "#2b405a",
              }}
            >
              <p style={{ margin: 0 }}>
                The Product Manager Accelerator Program is designed to support PM professionals
                through every stage of their careers. From students looking for entry-level jobs to
                Directors looking to take on a leadership role, our program has helped over
                hundreds of students fulfill their career aspirations.
              </p>

              <p style={{ margin: 0 }}>
                Our Product Manager Accelerator community are ambitious and committed. Through our
                program they have learnt, honed and developed new PM and leadership skills, giving
                them a strong foundation for their future endeavors.
              </p>

              <p style={{ margin: 0 }}>
                Here are the examples of services we offer. Check out our website (link under my
                profile) to learn more about our services.
              </p>

              <div style={{ display: "grid", gap: "14px" }}>
                <section>
                  <strong>🚀 PMA Pro</strong>
                  <p style={{ margin: "6px 0 0" }}>
                    End-to-end product manager job hunting program that helps you master
                    FAANG-level Product Management skills, conduct unlimited mock interviews, and
                    gain job referrals through our largest alumni network. 25% of our offers came
                    from tier 1 companies and get paid as high as $800K/year.
                  </p>
                </section>

                <section>
                  <strong>🚀 AI PM Bootcamp</strong>
                  <p style={{ margin: "6px 0 0" }}>
                    Gain hands-on AI Product Management skills by building a real-life AI product
                    with a team of AI Engineers, data scientists, and designers. We will also help
                    you launch your product with real user engagement using our 100,000+ PM
                    community and social media channels.
                  </p>
                </section>

                <section>
                  <strong>🚀 PMA Power Skills</strong>
                  <p style={{ margin: "6px 0 0" }}>
                    Designed for existing product managers to sharpen their product management
                    skills, leadership skills, and executive presentation skills.
                  </p>
                </section>

                <section>
                  <strong>🚀 PMA Leader</strong>
                  <p style={{ margin: "6px 0 0" }}>
                    We help you accelerate your product management career, get promoted to Director
                    and product executive levels, and win in the board room.
                  </p>
                </section>

                <section>
                  <strong>🚀 1:1 Resume Review</strong>
                  <p style={{ margin: "6px 0 0" }}>
                    We help you rewrite your killer product manager resume to stand out from the
                    crowd, with an interview guarantee.
                  </p>
                  <p style={{ margin: "6px 0 0" }}>
                    Get started by using our FREE killer PM resume template used by over 14,000
                    product managers.{" "}
                    <a
                      href="https://www.drnancyli.com/pmresume"
                      target="_blank"
                      rel="noreferrer"
                      style={linkStyle}
                    >
                      https://www.drnancyli.com/pmresume
                    </a>
                  </p>
                </section>

                <section>
                  <strong>🚀 Free Training and Courses</strong>
                  <p style={{ margin: "6px 0 0" }}>
                    We also published over 500+ free training and courses. Please go to my YouTube
                    channel{" "}
                    <a
                      href="https://www.youtube.com/c/drnancyli"
                      target="_blank"
                      rel="noreferrer"
                      style={linkStyle}
                    >
                      https://www.youtube.com/c/drnancyli
                    </a>{" "}
                    and Instagram <strong>@drnancyli</strong> to start learning for free today.
                  </p>
                </section>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value }) {
  return (
    <div
      style={{
        padding: "16px",
        borderRadius: "18px",
        background: "rgba(243, 247, 255, 0.92)",
        border: "1px solid rgba(18, 32, 51, 0.08)",
        display: "grid",
        gap: "8px",
      }}
    >
      <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", color: "#46617f" }}>
        {icon}
        <span>{label}</span>
      </div>
      <strong style={{ fontSize: "1.05rem" }}>{value}</strong>
    </div>
  );
}

const panelStyle = {
  background: "rgba(255, 255, 255, 0.72)",
  border: "1px solid rgba(18, 32, 51, 0.08)",
  backdropFilter: "blur(14px)",
  borderRadius: "28px",
  padding: "24px",
  boxShadow: "0 24px 60px rgba(27, 53, 87, 0.08)",
};

const exportButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  border: "1px solid rgba(18, 32, 51, 0.14)",
  borderRadius: "999px",
  padding: "10px 14px",
  background: "white",
  color: "#14263f",
  cursor: "pointer",
};

const errorBannerStyle = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
  borderRadius: "18px",
  padding: "14px 16px",
  background: "rgba(184, 34, 55, 0.1)",
  color: "#8a2334",
};

const subtleBlockStyle = {
  padding: "16px",
  borderRadius: "18px",
  background: "rgba(243, 247, 255, 0.92)",
  border: "1px solid rgba(18, 32, 51, 0.08)",
};

const subtleHeadingStyle = {
  marginTop: 0,
  marginBottom: "10px",
  fontSize: "0.95rem",
};

const linkStyle = {
  color: "#1f5eaf",
  textDecoration: "none",
  fontWeight: 600,
};

const videoLinkStyle = {
  display: "block",
  padding: "12px",
  borderRadius: "14px",
  background: "white",
  textDecoration: "none",
  color: "#14263f",
  border: "1px solid rgba(18, 32, 51, 0.08)",
};

const emptyTextStyle = {
  margin: 0,
  color: "#6c839d",
};
