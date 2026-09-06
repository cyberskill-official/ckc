import { BillingService } from "./billing";

export function processCheckout(userId: string, cart: { price: number; quantity: number }[]): boolean {
    const billing = new BillingService();
    const total = billing.calculateTotal(cart);
    return billing.charge(userId, total);
}
