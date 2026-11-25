export function add(a, b) {
  return a + b;
}

export class Counter {
  constructor() {
    this.value = 0;
  }

  inc() {
    this.value += 1;
    return this.value;
  }
}
