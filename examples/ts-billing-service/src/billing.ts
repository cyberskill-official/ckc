export class BillingService {
    calculateTotal(items: { price: number; quantity: number }[]): number {
        return items.reduce((acc, item) => acc + (item.price * item.quantity), 0);
    }

    charge(userId: string, amount: number): boolean {
        console.log(`Charging ${userId}: $${amount}`);
        return true;
    }
}
