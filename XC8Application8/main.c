#define F_CPU 8000000UL

#include <avr/io.h>
#include <util/delay.h>

#define DROWSY_THRESHOLD   614 // ~60% on PA0 (Tilt)
#define IMPACT_MODERATE    400 // ~40% on PA1 (Moderate Shock)
#define IMPACT_SEVERE      750 // ~75% on PA1 (Severe Crash)

#define BUZZER     PC0 // Pin 22 -> Buzzer
#define YELLOW_LED PC1 // Pin 23 -> Yellow LED

typedef enum {
	STATE_SAFE,
	STATE_DROWSY,
	STATE_CRASH
} SystemState;

void UART_Init(void) {
	UBRRH = 0;
	UBRRL = 51; // 9600 Baud
	UCSRB = (1 << TXEN);
	UCSRC = (1 << URSEL) | (1 << UCSZ1) | (1 << UCSZ0);
}

void UART_SendString(const char *str) {
	while (*str) {
		while (!(UCSRA & (1 << UDRE)));
		UDR = *str++;
	}
}

void ADC_Init(void) {
	ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1); // Enable ADC, Prescaler 64
}

// Multiplexer channel switch with settling delay
uint16_t ADC_Read(uint8_t channel) {
	ADMUX = (1 << REFS0) | (channel & 0x07); // Set AVCC & Select Channel
	_delay_us(100);                          // Delay for MUX channel settling
	ADCSRA |= (1 << ADSC);                   // Start Conversion
	while (ADCSRA & (1 << ADSC));            // Wait for Conversion
	return ADC;
}

int main(void) {
	uint16_t tilt_val = 0;
	uint16_t impact_val = 0;
	SystemState current_state = STATE_SAFE;
	SystemState previous_state = STATE_SAFE;

	DDRC |= (1 << BUZZER) | (1 << YELLOW_LED);
	PORTC &= ~((1 << BUZZER) | (1 << YELLOW_LED));

	UART_Init();
	ADC_Init();

	_delay_ms(150);
	UART_SendString("SAFE\r\n");

	while (1) {
		// Read PA0 (Head Tilt)
		tilt_val = ADC_Read(0);
		_delay_ms(5);

		// Read PA1 (Piezo Impact Force)
		impact_val = ADC_Read(1);
		_delay_ms(5);

		// 1. SEVERE CRASH (Impact Sensor > 75%)
		if (impact_val >= IMPACT_SEVERE) {
			current_state = STATE_CRASH;
			PORTC |= (1 << BUZZER);
			PORTC &= ~(1 << YELLOW_LED);
		}
		// 2. DROWSINESS / HEAD TILT (Tilt Sensor > 60%)
		else if (tilt_val >= DROWSY_THRESHOLD) {
			current_state = STATE_DROWSY;
			PORTC |= (1 << YELLOW_LED) | (1 << BUZZER);
		}
		// 3. SAFE STATE
		else {
			current_state = STATE_SAFE;
			PORTC &= ~((1 << BUZZER) | (1 << YELLOW_LED));
		}

		// Transmit state only on change
		if (current_state != previous_state) {
			if (current_state == STATE_CRASH) {
				UART_SendString("CRASH\r\n");
			}
			else if (current_state == STATE_DROWSY) {
				UART_SendString("DROWSY\r\n");
			}
			else if (current_state == STATE_SAFE) {
				UART_SendString("SAFE\r\n");
			}
			previous_state = current_state;
		}

		_delay_ms(40);
	}
}