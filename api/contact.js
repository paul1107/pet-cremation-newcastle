export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { name, phone, email, pet_type, collection, message, consent } = req.body || {};

  if (!name || !phone) {
    return res.status(400).json({ error: 'Please provide your name and phone number.' });
  }

  if (!consent) {
    return res.status(400).json({ error: 'Please consent to our privacy policy.' });
  }

  const fields = [
    ['Name', name],
    ['Phone', phone],
    ['Email', email || 'Not provided'],
    ['Pet', pet_type || 'Not specified'],
    ['Collection', collection || 'Not specified'],
    ['Message', message || 'None']
  ];

  const text = '🐾 *New Lead — Pet Cremation Newcastle*\n\n' +
    fields.map(([k, v]) => `*${k}:* ${v}`).join('\n') +
    `\n\n\_${new Date().toLocaleString('en-GB', { timeZone: 'Europe/London' })}\_`;

  try {
    const tgResp = await fetch(
      `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/sendMessage`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: process.env.TELEGRAM_CHAT_ID,
          text,
          parse_mode: 'Markdown',
          disable_web_page_preview: true
        })
      }
    );

    if (!tgResp.ok) {
      const err = await tgResp.text();
      console.error('Telegram error:', err);
      throw new Error('Telegram API error');
    }

    return res.status(200).json({
      success: true,
      message: 'Thank you. We will call you back shortly.'
    });
  } catch (error) {
    console.error('Form handler error:', error);
    return res.status(500).json({
      error: 'Something went wrong. Please call us on 0191 000 0000 instead.'
    });
  }
}
