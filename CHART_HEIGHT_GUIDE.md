# Chart Height Adjustment Guide

## 🎯 How to Change Net Worth Chart Heights

### Method 1: CSS Variables (Recommended - Easiest)
Edit the file: `portfolio/templates/general.html`

Find this section around line 130:
```css
/* CSS Variables for easy height adjustment */
:root {
    --chart-height-desktop: 600px;  /* 🎯 CHANGE THIS FOR DESKTOP HEIGHT */
    --chart-height-tablet: 500px;   /* 🎯 CHANGE THIS FOR TABLET HEIGHT */
    --chart-height-mobile: 400px;   /* 🎯 CHANGE THIS FOR MOBILE HEIGHT */
    --chart-height-small-mobile: 350px;  /* 🎯 CHANGE THIS FOR SMALL MOBILE HEIGHT */
}
```

**Just change the pixel values!** For example:
- Desktop: `600px` → `800px` for taller charts
- Mobile: `400px` → `300px` for shorter charts

### Method 2: Python Configuration
Edit the file: `portfolio/chart_config.py`

Find these lines:
```python
NETWORTH_CHART_HEIGHT_DESKTOP = 500  # Change this for desktop height
NETWORTH_CHART_HEIGHT_TABLET = 450   # Change this for tablet height  
NETWORTH_CHART_HEIGHT_MOBILE = 350   # Change this for mobile height
NETWORTH_CHART_HEIGHT_SMALL_MOBILE = 300  # Change this for small mobile height
```

### Method 3: Direct in Views (Advanced)
Edit the file: `portfolio/views.py`

Find the chart creation in the `general()` function around line 1540:
```python
height=NETWORTH_CHART_HEIGHT_DESKTOP,  # Easy to change chart height here
```

## 📱 Responsive Breakpoints
- **Desktop**: > 1024px
- **Tablet**: 768px - 1024px  
- **Mobile**: 480px - 768px
- **Small Mobile**: < 480px

## 🎨 Additional Customization
You can also adjust:
- Chart colors in `portfolio/chart_config.py`
- Margins and spacing
- Font sizes
- Background colors

## 💡 Tips
- **Desktop**: Use larger heights (500-800px) for better data visualization
- **Mobile**: Use smaller heights (300-400px) to save screen space
- **Test**: Always test on different screen sizes after making changes
- **Refresh**: Clear browser cache if changes don't appear immediately

## 🔄 Quick Test Heights
Try these values for different effects:

**Tall Charts (More Detail):**
- Desktop: `700px`
- Mobile: `450px`

**Compact Charts (Less Space):**
- Desktop: `400px` 
- Mobile: `300px`

**Balanced Charts (Recommended):**
- Desktop: `600px`
- Mobile: `400px` 