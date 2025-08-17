# Interdependent Privacy (IDP) Manager

The Interdependent Privacy (IDP) Manager enables users to set and enforce their privacy preferences through a connected contact provider. It also provides visibility into how the contact provider is using their personal data.

## Tech Stack

- **Frontend**: React Router, Vite, TypeScript
- **UI**: shadcn/ui, Tailwind CSS
- **Database**: SQLite with Drizzle ORM
- **Authentication**: JWT tokens with email OTP
- **OTP**: Amazon SES and SNS

## Development Setup

1. **Install Dependencies**

   ```bash
   pnpm install
   ```

2. **Start Development Server**

   ```bash
   pnpm dev
   ```

3. **Access the Application**
   - Open http://localhost:5173
   - Navigate to `/login` to test authentication

## Environment Variables

Create a `.env` file in the `web` directory by copying `.env.example`:

```bash
cp .env.example .env
```

Then update the values in your `.env` file.
This step requires an Amazon access key and a secret configured to access Amazon SES and SNS.

## Database

The app uses SQLite with Drizzle ORM for data persistence.

```bash
# Generate migrations
pnpm db:generate

# Run migrations
pnpm db:migrate

# Open database studio
pnpm db:studio
```

## Authentication Flow

1. **Request OTP**: User enters email address
   - Generates 6-digit OTP code
   - Returns temporary JWT token

2. **Verify OTP**: User enters verification code
   - Validates OTP code
   - Returns authentication JWT token

## Available Scripts

- `pnpm dev` - Start development server
- `pnpm build` - Build for production
- `pnpm start` - Start production server
- `pnpm db:generate` - Generate database migrations
- `pnpm db:migrate` - Run database migrations
- `pnpm db:studio` - Open database studio
