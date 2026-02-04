from .app import app


def ensure_daily_reports() -> int:
    with app.app_context():
        return 0


def main() -> None:
    created = ensure_daily_reports()
    print(f"daily_reports_created={created}")


if __name__ == "__main__":
    main()
