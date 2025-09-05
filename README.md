# NYC Events Sync - Odoo 18 Module

Automatically import all public events in New York City from the Ticketmaster Discovery API and display them on your Odoo website.

## 🎯 Features

- **Automatic Event Import**: Fetches all NYC events from Ticketmaster Discovery API
- **All Categories**: Includes Music, Sports, Arts, Theatre, and all other event types
- **Auto-Sync**: Runs every 5 hours to keep events updated
- **Manual Sync**: One-click manual sync from Odoo settings
- **Website Integration**: Events appear on standard Odoo Website → Events pages
- **Rich Event Data**: Includes images, venue information, dates, and external ticket links
- **Smart Venue Management**: Automatically creates venue partners with full address data

## 📋 Requirements

- **Odoo 18.0**
- **Dependencies**: `event`, `website_event` modules
- **Ticketmaster API Key**: Free tier available (5,000 requests/day)

## 🚀 Installation

### 1. Download Module
```bash
git clone https://github.com/waqasmustafa/nyc_events_sync.git
# or download and extract to your Odoo addons directory
```

### 2. Install in Odoo
1. Go to **Apps** → **Update Apps List**
2. Search for "NYC Events Sync"
3. Click **Install**

### 3. Get Ticketmaster API Key
1. Visit [Ticketmaster Developer Portal](https://developer.ticketmaster.com/)
2. Create account and request API key
3. Free tier: 5,000 requests per day (perfect for this module)

## ⚙️ Configuration

### 1. Enter API Key
1. Go to **Settings** → **General Settings**
2. Find **"NYC Events Sync"** section
3. Enter your Ticketmaster API Key
4. Click **"Fetch NYC Events"**

### 2. Automatic Sync
- Sync runs automatically every 5 hours
- No additional configuration needed
- Events are auto-published to website

## 🎮 Usage

### Manual Sync
1. **Settings** → **General Settings**
2. **NYC Events Sync** section
3. Click **"Fetch NYC Events"** button
4. See success notification with event count

### View Events
1. **Website** → **Events** (frontend)
2. **Events** → **Events** (backend management)

### Event Details
Each imported event includes:
- ✅ **Event Name & Description**
- ✅ **Date & Time**
- ✅ **Venue Information**
- ✅ **Event Images**
- ✅ **Category** (Music, Sports, Arts, etc.)
- ✅ **External Ticket Link** (Buy Tickets button)

## 🔧 Technical Details

### API Integration
- **Source**: Ticketmaster Discovery API v2
- **Endpoint**: `https://app.ticketmaster.com/discovery/v2/events.json`
- **Filters**: `city=New York, countryCode=US`
- **Rate Limits**: 5 requests/second, 5,000/day
- **Pagination**: Handles API pagination automatically

### Data Mapping
| Ticketmaster Field | Odoo Field | Description |
|-------------------|------------|-------------|
| `name` | `name` | Event title |
| `dates.start.dateTime` | `date_begin` | Start date/time |
| `dates.end.dateTime` | `date_end` | End date/time (defaults to start + 2h) |
| `url` | `external_url` | Ticketmaster ticket link |
| `venues[0].name` | `venue_name` | Venue name |
| `classifications` | `event_category` | Event category |
| `images[0].url` | `image_1920` | Event image |
| `id` | `ticketmaster_id` | Unique identifier |

### Database Schema
The module extends `event.event` with additional fields:
- `ticketmaster_id`: Unique Ticketmaster event ID
- `external_url`: Link to buy tickets
- `ticketmaster_status`: Event status (onsale, cancelled, etc.)
- `event_category`: Event category from Ticketmaster
- `venue_name`: Venue name
- `last_synced_at`: Last sync timestamp

## 📁 File Structure

```
nyc_events_sync/
├── __manifest__.py              # Module configuration
├── __init__.py                  # Module initialization
├── models/
│   ├── __init__.py
│   ├── nyc_events_sync.py      # Main sync logic
│   └── res_config_settings.py  # Settings configuration
├── views/
│   ├── event_backend_views.xml  # Backend event form
│   ├── res_config_settings_views.xml  # Settings page
│   └── website_event_templates.xml    # Website templates
├── data/
│   ├── ir_actions_server.xml    # Manual sync action
│   └── ir_cron.xml             # Automatic sync schedule
└── security/
    └── ir.model.access.csv     # Access permissions
```

## 🔄 Sync Process

### Automatic Sync (Every 5 Hours)
1. **Cron Job** triggers `cron_sync_nyc_events()`
2. **API Call** fetches events from Ticketmaster
3. **Data Processing** maps Ticketmaster data to Odoo format
4. **Database Update** creates/updates event records
5. **Venue Management** creates venue partners
6. **Image Download** fetches and stores event images
7. **Publishing** auto-publishes events to website

### Manual Sync
1. **User Action** clicks "Fetch NYC Events" button
2. **Same Process** as automatic sync
3. **User Notification** shows success message with counts

## 🛠️ Troubleshooting

### Common Issues

#### 1. API Key Error
```
Error: No Ticketmaster API key found
```
**Solution**: Enter valid API key in Settings → NYC Events Sync

#### 2. Rate Limit Error
```
Error: 429 Too Many Requests
```
**Solution**: Module handles this automatically with 5-second delays

#### 3. Database Constraint Error
```
Error: null value in column "date_end"
```
**Solution**: Fixed in latest version - events without end dates get start date + 2 hours

#### 4. Paging Limit Error
```
Error: DIS1035 - Max paging depth exceeded
```
**Solution**: Module now uses safe pagination limits

### Debug Mode
Check Odoo logs for detailed error information:
```bash
tail -f /var/log/odoo/odoo-server.log
```

## 📊 Performance

### API Limits
- **Free Tier**: 5,000 requests/day
- **Sync Frequency**: Every 5 hours
- **Estimated Usage**: ~24 requests/day (well within limits)

### Database Impact
- **Event Records**: Standard Odoo event records
- **Venue Partners**: Reuses existing venues when possible
- **Images**: Stored in Odoo's standard image fields

## 🔒 Security

- **API Key**: Stored securely in `ir.config_parameter`
- **Access Control**: System administrators only
- **Data Validation**: All input data is sanitized
- **Error Handling**: Comprehensive error logging

## 📈 Monitoring

### Success Metrics
- **Events Created**: New events imported
- **Events Updated**: Existing events refreshed
- **Events Skipped**: Duplicates or invalid data
- **Sync Status**: Last successful sync timestamp

### Log Messages
```
INFO: Fetched 10 events from Ticketmaster (limited to 10 for testing)
INFO: NYC Events Sync: created=8 updated=2 skipped=0 total=10
```

## 🚀 Future Enhancements

- [ ] Support for other cities
- [ ] Event filtering by category
- [ ] Custom sync schedules
- [ ] Event analytics dashboard
- [ ] Multi-language support

## 📞 Support

### Issues
Report issues on [GitHub Issues](https://github.com/waqasmustafa/nyc_events_sync/issues)

### Documentation
- [Ticketmaster API Docs](https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/)
- [Odoo Events Module](https://www.odoo.com/documentation/18.0/applications/website/website/events.html)

## 📄 License

LGPL-3 - See LICENSE file for details

## 👨‍💻 Author

**Waqas Mustafa**
- GitHub: [@waqasmustafa](https://github.com/waqasmustafa)
- Email: [Your Email]

---

## 🎉 Quick Start

1. **Install** the module in Odoo 18
2. **Get** a free Ticketmaster API key
3. **Enter** the API key in Settings
4. **Click** "Fetch NYC Events"
5. **View** events on your website!

**That's it!** Your website now automatically displays all NYC events from Ticketmaster. 🎊
