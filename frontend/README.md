# CollabEdit - React Frontend

Modern React frontend for the Collaborative Editing System.

## Project Structure

```
frontend/
├── public/
│   └── index.html          # HTML template
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── Alert.js        # Notification alerts
│   │   ├── Avatar.js       # User avatars
│   │   ├── Button.js       # Button component
│   │   ├── DocumentList.js # Document listing
│   │   ├── Editor.js       # Main text editor
│   │   ├── Header.js       # Top navigation
│   │   ├── Input.js        # Form inputs
│   │   ├── Loading.js      # Loading states
│   │   ├── Modal.js        # Modal dialogs
│   │   ├── Sidebar.js      # Left sidebar
│   │   └── VersionHistory.js # Version panel
│   ├── contexts/
│   │   └── AuthContext.js  # Authentication state
│   ├── hooks/              # Custom React hooks
│   ├── pages/
│   │   ├── DashboardPage.js # Main app page
│   │   └── LoginPage.js    # Auth page
│   ├── services/
│   │   ├── api.js          # Backend API calls
│   │   └── websocket.js    # WebSocket handling
│   ├── styles/
│   │   └── index.css       # Global styles
│   ├── App.js              # Root component
│   └── index.js            # Entry point
└── package.json
```

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- Backend server running on port 8000

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm start
```

The app will open at http://localhost:3000

### Production Build

```bash
npm run build
```

## Key Concepts

### Component Architecture

Components are organized by:
- **Reusable Components** (`/components`): Generic UI elements
- **Page Components** (`/pages`): Full page views
- **Context Providers** (`/contexts`): Global state management

### State Management

- **AuthContext**: Manages user authentication state globally
- **Local State**: Component-specific state using `useState`
- **Derived State**: Computed values from props/state

### API Layer

The `services/api.js` module provides:
- Clean abstraction for backend calls
- Automatic token handling
- Consistent error handling

### Real-time Updates

WebSocket service (`services/websocket.js`) handles:
- Connection management
- Event subscriptions
- Automatic reconnection
- Document room joining

## Design Patterns

1. **Container/Presenter**: Pages contain logic, components present UI
2. **Custom Hooks**: Reusable stateful logic
3. **Context API**: Global state without prop drilling
4. **Compound Components**: Related components working together

## Styling Approach

- CSS Variables for theming
- CSS Modules pattern (co-located CSS files)
- Mobile-first responsive design
- Consistent spacing and typography scale
